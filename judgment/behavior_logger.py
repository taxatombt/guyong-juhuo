# behavior_logger.py — 途径3：juhuo agent 行为日志层
"""
记录 juhuo 作为 agent 的工具调用行为，补充 experiences 表。

P2 目标：途径3 = "juhuo 帮用户做事（查资料/执行任务），积累行为数据"

三个信息途径完整架构：
  途径1 biography   → 用户自述生平（静态事实）
  途径2 experiences → 用户通过 juhuo 做过的决策（outcome 验证）
  途径3 behavior    → juhuo 实际调用了哪些工具，结果如何 ← 本文件

核心设计：
- 新增 experiences 表列：action_channel / tool_calls / execution_result / perception_summary
- router.py 调用 judgment → 记录 action_channel="judgment"
- action_executor → 执行通道 → 记录 tool_calls + execution_result
- web console /api/task → 执行感知工具 → 记录 perception_summary

数据流：
  用户提交任务 → router.check10d() → experiences.save_experience()
                                      ↓
  action_executor.execute() → log_agent_behavior(..., tool_calls=[...])
                                      ↓
  experiences 表更新 → future find_similar() 命中时含工具上下文
"""

import json
import time
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# ── 路径配置 ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "judgment_data" / "juhuo_judgment.db"


# ── 执行通道枚举 ────────────────────────────────────────────────────────────
class ActionChannel(str, Enum):
    """juhuo 执行任务的通道"""
    JUDGMENT     = "judgment"       # 仅做判断，无执行
    BENCHMARK    = "benchmark"     # GDPVal benchmark 验证
    WEB_SEARCH   = "web_search"    # 网页搜索
    WEB_ANALYZE  = "web_analyze"   # 网页内容分析
    PERCEPTION   = "perception"    # 感知工具（PDF/邮件/RSS）
    HERMES       = "hermes"        # 委托 Hermes agent
    CLAUDE_CODE  = "claude_code"   # 委托 Claude Code
    MANUAL       = "manual"        # CLI 手动调用


# ── Dataclass ────────────────────────────────────────────────────────────────
@dataclass
class ToolCall:
    """一次工具调用"""
    tool_name: str           # "web_search" / "pdf_read" / "judgment.check10d" ...
    arguments: Dict[str, Any]  # 入参（脱敏：移除敏感字段）
    result_summary: str      # 结果摘要（截断到200字）
    duration_ms: float       # 耗时毫秒
    status: str              # "success" / "failed" / "timeout"


@dataclass
class AgentBehavior:
    """一次 agent 行为的完整记录"""
    behavior_id: str         # 唯一标识
    chain_id: str            # 对应 judgment snapshot（可为空）
    channel: ActionChannel
    task_text: str           # 用户原始任务
    verdict: str              # 判断结论（若有）
    confidence: float         # 置信度（若有）
    tool_calls: List[ToolCall]
    execution_result: str     # 执行层最终结果（摘要）
    perception_summary: str   # 若有感知内容，摘要
    outcome_score: float     # 0.0~1.0 事后验证
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        d["tool_calls"] = [
            {**tc.__dict__, "arguments": _sanitize_args(tc.arguments)}
            for tc in self.tool_calls
        ]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def _sanitize_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏：移除敏感字段"""
    sensitive = {"password", "token", "secret", "api_key", "key", "auth"}
    return {
        k: ("***REDACTED***" if any(s in k.lower() for s in sensitive) else v)
        for k, v in args.items()
        if not (isinstance(v, str) and len(v) > 500)  # 截断超长字符串
    }


# ── DB 操作 ─────────────────────────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate():
    """确保 experiences 表有 behavior 相关列"""
    conn = _get_conn()
    for col, dtype in [
        ("action_channel",   "TEXT"),
        ("tool_calls",       "TEXT"),
        ("execution_result", "TEXT"),
        ("perception_summary", "TEXT"),
        ("behavior_id",      "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE experiences ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass  # 列已存在
    conn.commit()
    conn.close()


# ── 核心 API ────────────────────────────────────────────────────────────────

def log_agent_behavior(
    task_text: str,
    channel: ActionChannel,
    verdict: str = "",
    confidence: float = 0.0,
    chain_id: str = "",
    tool_calls: Optional[List[ToolCall]] = None,
    execution_result: str = "",
    perception_summary: str = "",
    outcome_score: float = -1.0,  # -1 = 未验证
    user_id: str = "default",
) -> str:
    """
    记录一次 agent 行为，更新 experiences 表。

    行为记录流程：
      1. router.check10d() → call log_agent_behavior(channel="judgment")
         → experiences.save_experience() 已写入 → 用 task_hash 定位行

      2. action_executor.execute() → call log_agent_behavior(channel=WEB_SEARCH/HERMES/...)
         → 更新同一行：tool_calls + execution_result

      3. 用户确认结果 → record_outcome() → outcome_score 写入
         → future find_similar() 命中时同时含判断和执行上下文

    Args:
        task_text: 用户任务文本
        channel: 执行通道
        verdict: 判断结论（有的话）
        confidence: 置信度
        chain_id: judgment snapshot 的 chain_id
        tool_calls: 工具调用列表
        execution_result: 执行结果摘要
        perception_summary: 感知内容摘要（网页分析结果等）
        outcome_score: 事后验证分数（0.0~1.0，-1=未验证）
        user_id: 用户标识

    Returns:
        behavior_id: 生成的唯一行为ID
    """
    _migrate()

    import hashlib
    behavior_id = str(uuid.uuid4())[:16]
    now = datetime.now().isoformat()
    task_hash = hashlib.md5(f"{user_id}::{task_text}".encode()).hexdigest()[:24]

    tc_json = json.dumps(
        [{**tc.__dict__, "arguments": _sanitize_args(tc.arguments)} for tc in (tool_calls or [])],
        ensure_ascii=False
    )

    conn = _get_conn()
    try:
        # 尝试 UPDATE 已存在的行
        n = conn.execute("""
            UPDATE experiences
            SET action_channel=?,
                tool_calls=?,
                execution_result=?,
                perception_summary=?,
                behavior_id=?,
                outcome_score=CASE WHEN ? >= 0 THEN ? ELSE outcome_score END
            WHERE user_id=? AND task_hash=?
        """, (
            channel.value,
            tc_json,
            execution_result[:1000],  # 截断
            perception_summary[:500],
            behavior_id,
            outcome_score,
            outcome_score,
            user_id,
            task_hash,
        )).rowcount

        if n == 0:
            # 行不存在 → 创建新 experience + behavior 记录
            conn.execute("""
                INSERT INTO experiences
                (user_id, task_hash, task_text, conclusion, confidence,
                 action_channel, tool_calls, execution_result,
                 perception_summary, behavior_id, outcome_score, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id, task_hash, task_text, verdict or "(无结论)",
                confidence, channel.value, tc_json,
                execution_result[:1000], perception_summary[:500],
                behavior_id, outcome_score if outcome_score >= 0 else None,
                now,
            ))
        conn.commit()
    finally:
        conn.close()

    return behavior_id


def get_behavior(behavior_id: str) -> Optional[Dict[str, Any]]:
    """根据 behavior_id 查询行为记录"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM experiences WHERE behavior_id=?",
        (behavior_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in conn.execute("SELECT * FROM experiences LIMIT 0").description]
    conn.close()
    return dict(zip(cols, row))


def get_recent_behaviors(
    user_id: str = "default",
    channel: Optional[ActionChannel] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """查询最近的 agent 行为记录"""
    conn = _get_conn()
    if channel:
        rows = conn.execute("""
            SELECT behavior_id, action_channel, conclusion,
                   tool_calls, execution_result, perception_summary,
                   outcome_score, created_at
            FROM experiences
            WHERE user_id=? AND action_channel=? AND behavior_id IS NOT NULL
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, channel.value, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT behavior_id, action_channel, conclusion,
                   tool_calls, execution_result, perception_summary,
                   outcome_score, created_at
            FROM experiences
            WHERE user_id=? AND behavior_id IS NOT NULL
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    conn.close()
    cols = ["behavior_id", "action_channel", "conclusion",
            "tool_calls", "execution_result", "perception_summary",
            "outcome_score", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_behavior_stats(user_id: str = "default") -> Dict[str, Any]:
    """统计 juhuo 作为 agent 的行为模式"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT action_channel, COUNT(*) as cnt,
               AVG(CASE WHEN outcome_score IS NOT NULL THEN outcome_score ELSE NULL END) as avg_outcome,
               COUNT(CASE WHEN outcome_score IS NOT NULL THEN 1 END) as verified_cnt
        FROM experiences
        WHERE user_id=? AND action_channel IS NOT NULL
        GROUP BY action_channel
    """, (user_id,)).fetchall()
    conn.close()
    return {
        "total_behaviors": sum(r[1] for r in rows),
        "channel_breakdown": {
            r[0]: {"count": r[1], "avg_outcome": r[2], "verified": r[3]}
            for r in rows
        },
    }