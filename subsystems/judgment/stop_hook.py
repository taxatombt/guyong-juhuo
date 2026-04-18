#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stop_hook.py — Juhuo Stop Hook事件捕获

核心改进: 任务结束被动捕获行为，生成instinct记录

像ECC那样:
- 每次对话结束/任务结束，被动捕获行为
- 不是feedback_system主动调用
- 是completion事件触发的
"""

import json, time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from judgment.judgment_db import get_conn


class EventType(Enum):
    TASK_START = "task_start"
    TASK_END = "task_end"
    JUDGMENT_CALLED = "judgment_called"
    JUDGMENT_RESULT = "judgment_result"
    VERDICT_RECEIVED = "verdict_received"
    TOOL_CALLED = "tool_called"


@dataclass
class Instinct:
    id: str
    event_type: str
    trigger: str
    action: str
    outcome: str
    lesson: str
    confidence: float
    use_count: int = 0
    last_used: str = ""
    tags: List[str] = None
    created_at: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.id:
            self.id = f"inst_{int(time.time()*1000)}"


@dataclass
class Trajectory:
    session_id: str
    events: List[Dict]
    judgments: List[Dict]
    verdicts: List[Dict]
    duration: float
    outcome: str
    lessons: List[str] = None

    def __post_init__(self):
        if self.lessons is None:
            self.lessons = []


class StopHook:
    """停止钩子：任务结束时被动捕获行为"""

    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"s_{int(time.time()*1000)}"
        self.events: List[Dict] = []
        self.judgments: List[Dict] = []
        self.verdicts: List[Dict] = []
        self.tool_calls: List[Dict] = []
        self.start_time = time.time()

    def capture_event(self, event_type: str, data: Dict):
        self.events.append({
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        })

    def capture_judgment(self, task: str, dimensions: List[str], result: Dict, rule_precheck: Dict = None):
        self.judgments.append({
            "task": task[:200],
            "dimensions": dimensions,
            "result_summary": {"decision": result.get("decision"), "scores": result.get("scores")},
            "rule_precheck": rule_precheck,
            "timestamp": datetime.now().isoformat(),
        })

    def capture_verdict(self, chain_id: str, correct: bool, notes: str = ""):
        self.verdicts.append({
            "chain_id": chain_id,
            "correct": correct,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        })
        # ── 闭环：触发 receive_verdict 更新信念 ──────────────────────
        try:
            from judgment.closed_loop import receive_verdict
            receive_verdict(chain_id=chain_id, correct=correct, notes=notes)
        except Exception:
            pass  # 不因闭环失败影响主流程

    def capture_tool_call(self, tool_name: str, args: Dict, result: Any):
        self.tool_calls.append({
            "tool": tool_name,
            "args": {k: str(v)[:100] for k, v in args.items()},
            "timestamp": datetime.now().isoformat(),
        })

    def analyze_trajectory(self) -> Trajectory:
        duration = time.time() - self.start_time
        if self.verdicts:
            correct_count = sum(1 for v in self.verdicts if v["correct"])
            outcome = "success" if correct_count > len(self.verdicts) / 2 else "failure"
        else:
            outcome = "unknown"

        lessons = []
        for v in self.verdicts:
            if v["correct"]:
                lessons.append(f"正确: {v['chain_id'][:20]}")
            else:
                lessons.append(f"错误: {v['chain_id'][:20]}")

        return Trajectory(
            session_id=self.session_id,
            events=self.events,
            judgments=self.judgments,
            verdicts=self.verdicts,
            duration=duration,
            outcome=outcome,
            lessons=lessons,
        )

    def finalize(self) -> List[Instinct]:
        trajectory = self.analyze_trajectory()
        instincts = []

        # 从judgment生成instinct
        for j in self.judgments:
            instinct = Instinct(
                id=f"inst_{int(time.time()*1000)}_{len(instincts)}",
                event_type=EventType.JUDGMENT_RESULT.value,
                trigger=f"任务: {j['task'][:50]}",
                action=f"判断: {j['dimensions']}",
                outcome=trajectory.outcome,
                lesson=f"规则预检: {len((j.get('rule_precheck') or {}).get('llm_dimensions', []))}个维度需LLM",
                confidence=0.5,
            )
            instincts.append(instinct)

        # 从verdict生成instinct
        for v in self.verdicts:
            instinct = Instinct(
                id=f"inst_{int(time.time()*1000)}_{len(instincts)}",
                event_type=EventType.VERDICT_RECEIVED.value,
                trigger=f"判断链: {v['chain_id'][:20]}",
                action="receive_verdict",
                outcome="正确" if v["correct"] else "错误",
                lesson=v.get("notes", "从反馈学习"),
                confidence=0.8 if v["correct"] else 0.6,
            )
            instincts.append(instinct)

        # 轨迹级instinct
        if trajectory.duration > 60 or len(self.tool_calls) > 5:
            instincts.append(Instinct(
                id=f"inst_{int(time.time()*1000)}_{len(instincts)}",
                event_type=EventType.TOOL_CALLED.value,
                trigger=f"时长{trajectory.duration:.0f}秒, 工具{len(self.tool_calls)}次",
                action=f"轨迹分析",
                outcome=trajectory.outcome,
                lesson="; ".join(trajectory.lessons[:3]) or "需要更多数据",
                confidence=0.6,
            ))

        self._save_instincts(instincts)
        return instincts

    def _save_instincts(self, instincts: List[Instinct]):
        with get_conn() as c:
            for inst in instincts:
                c.execute("""
                    INSERT OR IGNORE INTO instinct_records 
                    (id, event_type, trigger, action, outcome, lesson, confidence, use_count, last_used, tags, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    inst.id, inst.event_type, inst.trigger, inst.action, inst.outcome,
                    inst.lesson, inst.confidence, inst.use_count, inst.last_used,
                    json.dumps(inst.tags), inst.created_at,
                ))
            c.commit()


# ── 全局实例 ────────────────────────────────────────────────────────
_global_hook: Optional[StopHook] = None


def get_stop_hook() -> StopHook:
    global _global_hook
    if _global_hook is None:
        _global_hook = StopHook()
    return _global_hook


def capture_judgment(task: str, dimensions: List[str], result: Dict, rule_precheck: Dict = None):
    get_stop_hook().capture_judgment(task, dimensions, result, rule_precheck)


def capture_verdict(chain_id: str, correct: bool, notes: str = ""):
    get_stop_hook().capture_verdict(chain_id, correct, notes)


def capture_tool_call(tool_name: str, args: Dict, result: Any):
    get_stop_hook().capture_tool_call(tool_name, args, result)


def finalize_session() -> List[Instinct]:
    global _global_hook
    if _global_hook is None:
        return []
    instincts = _global_hook.finalize()
    _global_hook = None
    return instincts


# ── 数据库表 ───────────────────────────────────────────────────────
def init_instinct_db():
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS instinct_records (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                trigger TEXT,
                action TEXT,
                outcome TEXT,
                lesson TEXT,
                confidence REAL DEFAULT 0.5,
                use_count INTEGER DEFAULT 0,
                last_used TEXT,
                tags TEXT,
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_instinct_event_type ON instinct_records(event_type);
            CREATE INDEX IF NOT EXISTS idx_instinct_confidence ON instinct_records(confidence DESC);
        """)
        c.commit()


def get_instincts(min_confidence: float = 0.5, limit: int = 20) -> List[Dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT * FROM instinct_records 
            WHERE confidence >= ? 
            ORDER BY confidence DESC, use_count DESC 
            LIMIT ?
        """, (min_confidence, limit)).fetchall()
        return [dict(r) for r in rows]


def promote_instinct(instinct_id: str) -> bool:
    with get_conn() as c:
        c.execute("""
            UPDATE instinct_records SET confidence = MIN(1.0, confidence + 0.1)
            WHERE id = ?
        """, (instinct_id,))
        c.commit()
        return c.total_changes > 0


init_instinct_db()


# ── 数据库表 ───────────────────────────────────────────────────────
def init_instinct_db():
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS instinct_records (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                trigger TEXT,
                action TEXT,
                outcome TEXT,
                lesson TEXT,
                confidence REAL DEFAULT 0.5,
                use_count INTEGER DEFAULT 0,
                last_used TEXT,
                tags TEXT,
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_instinct_event_type ON instinct_records(event_type);
            CREATE INDEX IF NOT EXISTS idx_instinct_confidence ON instinct_records(confidence DESC);
        """)
        c.commit()


def get_instincts(min_confidence: float = 0.5, limit: int = 20) -> List[Dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT * FROM instinct_records 
            WHERE confidence >= ? 
            ORDER BY confidence DESC, use_count DESC 
            LIMIT ?
        """, (min_confidence, limit)).fetchall()
