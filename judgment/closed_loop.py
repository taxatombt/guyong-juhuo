"""
judgment/closed_loop.py — 因果链闭环系统

judgment 输出 → 因果链记录 → self_model 更新 → 下次置信度调整
    ↑
    ← ← ← ← ← ← ← ← ← ← ← ← 事后验证信号（反向修正）

设计原则：
- 文件有界：SQLite rolling buffer，100条上限
- 更新有界：单次变化 ≤0.15，衰减系数 0.1
- 饱和保护：置信度 >0.95 或 <0.05 时停止更新
"""

import sqlite3
import json
import time
import hashlib
import os
from threading import Lock
from typing import Optional, Dict, List, Any

# ── 数据库路径 ──────────────────────────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'evolutions', 'juhuo.db')
_DIR = os.path.dirname(_DB_PATH)

MAX_CHAIN = 100          # rolling buffer 上限
_DECAY = 0.1             # 衰减系数
_MAX_DELTA = 0.15        # 单次最大变化
_SATURATE_HIGH = 0.95   # 饱和上限
_SATURATE_LOW = 0.05    # 饱和下限

# ── 10个维度 ID ────────────────────────────────────────────────────────────
DIM_IDS = [
    "cognitive", "game_theory", "economic", "dialectical",
    "emotional", "intuitive", "moral", "social",
    "temporal", "metacognitive"
]

_lock = Lock()


def _get_conn():
    os.makedirs(_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    """初始化数据库表（幂等）"""
    conn = _get_conn()
    try:
        # 因果链 rolling buffer
        conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_chain (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id    TEXT    NOT NULL,
                ts          REAL    NOT NULL,
                task_hash   TEXT    NOT NULL,
                task_text   TEXT,
                dimensions  TEXT,
                outcome     REAL,
                corrected   INTEGER DEFAULT 0,
                notes       TEXT
            )
        """)
        # 维度信念（有界更新）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dimension_beliefs (
                dim_id      TEXT PRIMARY KEY,
                belief      REAL    NOT NULL DEFAULT 0.5,
                hit_count   INTEGER NOT NULL DEFAULT 0,
                miss_count  INTEGER NOT NULL DEFAULT 0,
                last_id     TEXT
            )
        """)
        # 初始化10个维度的信念（如果不存在）
        for d in DIM_IDS:
            conn.execute(
                "INSERT OR IGNORE INTO dimension_beliefs (dim_id, belief, hit_count, miss_count) VALUES (?, 0.5, 0, 0)",
                (d,)
            )
        conn.commit()
    finally:
        conn.close()


# ── 闭环 Hook：verdict → 各子系统 ────────────────────────────────────────

def _trigger_fitness_record(chain_id: str, task_text: str,
                              correct: bool, notes: str,
                              changes: Dict) -> None:
    """Hook: receive_verdict → FitnessBaseline.record_from_verdict"""
    try:
        from judgment.fitness_baseline import FitnessBaseline
        fb = FitnessBaseline()
        fb.record_from_verdict(chain_id, task_text, correct, notes, changes)
    except Exception:
        pass  # 孤立失败不影响主流程


def _trigger_curiosity_from_verdict(chain_id: str, task_text: str,
                                     correct: bool,
                                     changes: Optional[Dict]) -> None:
    """Hook: receive_verdict → curiosity_engine.trigger_from_verdict
    PAD A > 0.7 → 自由探索概率提升"""
    try:
        # 尝试获取 emotion_system 的 PAD 状态
        pad_state = _get_pad_state_from_emotion(task_text, correct)
        from curiosity.curiosity_engine import trigger_from_verdict
        trigger_from_verdict(chain_id, task_text, correct, pad_state, changes)
    except Exception:
        pass  # 孤立失败不影响主流程


def _get_pad_state_from_emotion(task_text: str, correct: bool) -> Dict[str, float]:
    """从 emotion_system 获取当前 PAD 状态"""
    try:
        from emotion_system.emotion_system import EmotionSystem
        es = EmotionSystem()
        # 构造最小 judgment_result 来触发情绪检测
        result = {"task": task_text, "dim_confidence": {}, "meta": {}}
        es.detect_emotion(task_text, result)
        return es.get_pad_state()
    except Exception:
        # fallback：基于 verdict 正确性推断 PAD
        return {"P": 0.6 if correct else 0.3, "A": 0.6, "D": 0.5}


# ── 记录单条判断因果链 ───────────────────────────────────────────────────────

def _hash_task(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def record_judgment(
    task_text: str,
    dimensions: List[str],
    weights: Dict[str, float],
    reasoning: Dict[str, str],
    outcome: Optional[float] = None,
) -> str:
    """
    记录一次判断的因果链。
    返回 chain_id（供后续 receive_verdict 引用）。
    """
    chain_id = f"j_{int(time.time()*1000)}"
    task_hash = _hash_task(task_text)

    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO causal_chain (chain_id, ts, task_hash, task_text, dimensions, outcome)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chain_id,
            time.time(),
            task_hash,
            task_text[:500] if task_text else "",
            json.dumps({"dims": dimensions, "weights": weights, "reasoning": reasoning}, ensure_ascii=False),
            outcome,
        ))

        # Rolling：超过100条删最旧的
        conn.execute("""
            DELETE FROM causal_chain
            WHERE id NOT IN (
                SELECT id FROM causal_chain ORDER BY ts DESC LIMIT ?
            )
        """, (MAX_CHAIN,))

        conn.commit()
    finally:
        conn.close()

    return chain_id


# ── 接收事后验证信号 ────────────────────────────────────────────────────────

def receive_verdict(
    chain_id: Optional[str] = None,
    task_text: Optional[str] = None,
    correct: bool = True,
    notes: str = "",
) -> Dict[str, Any]:
    """
    接收事后验证信号，更新维度信念（反向修正）。

    参数：
        chain_id: 判断记录ID（优先用它定位）
        task_text: 任务文本（当 chain_id 不可用时模糊匹配）
        correct: 判断是否正确
        notes: 可选备注

    返回：各维度的信念变化情况
    """
    conn = _get_conn()
    try:
        # 定位目标记录
        target = None
        if chain_id:
            cur = conn.execute(
                "SELECT id, dimensions FROM causal_chain WHERE chain_id = ? AND corrected = 0",
                (chain_id,)
            )
            target = cur.fetchone()
        elif task_text:
            h = _hash_task(task_text)
            cur = conn.execute(
                "SELECT id, dimensions FROM causal_chain WHERE task_hash = ? AND corrected = 0 ORDER BY ts DESC LIMIT 1",
                (h,)
            )
            target = cur.fetchone()

        if not target:
            return {"updated": False, "reason": "no_record_found"}

        rec_id, dims_json = target
        dims_data = json.loads(dims_json)

        # 计算信念修正
        correction = 1.0 if correct else -1.0
        changes = {}

        for dim_id in dims_data.get("dims", []):
            cur = conn.execute(
                "SELECT belief, hit_count, miss_count FROM dimension_beliefs WHERE dim_id = ?",
                (dim_id,)
            )
            row = cur.fetchone()
            if not row:
                continue

            belief, hit, miss = row

            # 有界更新
            delta = _DECAY * correction
            delta = max(-_MAX_DELTA, min(_MAX_DELTA, delta))
            new_belief = belief + delta

            # 饱和保护
            new_belief = max(_SATURATE_LOW, min(_SATURATE_HIGH, new_belief))

            new_hit = hit + (1 if correct else 0)
            new_miss = miss + (0 if correct else 1)

            conn.execute(
                "UPDATE dimension_beliefs SET belief=?, hit_count=?, miss_count=?, last_id=? WHERE dim_id=?",
                (new_belief, new_hit, new_miss, chain_id, dim_id)
            )

            changes[dim_id] = {
                "belief_before": round(belief, 4),
                "belief_after": round(new_belief, 4),
                "delta": round(delta, 4),
                "hit": new_hit,
                "miss": new_miss,
            }

        # 标记已修正
        conn.execute(
            "UPDATE causal_chain SET corrected = 1, notes = ? WHERE id = ?",
            (notes[:200], rec_id)
        )
        conn.commit()

        # ── 三个闭环 hook（在 conn.close() 之前，finally 之前）─────────────
        # 1. FitnessBaseline ← verdict 记录
        _trigger_fitness_record(chain_id, task_text, correct, notes, changes)
        # 2. Curiosity       ← 情绪驱动好奇心
        _trigger_curiosity_from_verdict(chain_id, task_text, correct, changes)
        # 3. CausalMemory    ← 事后验证反馈（通过 closed_loop 作为唯一数据源）

        return {"updated": True, "chain_id": chain_id, "changes": changes}
    finally:
        conn.close()


# ── 读取信念调整值 ─────────────────────────────────────────────────────────

def get_prior_adjustments() -> Dict[str, float]:
    """
    返回各维度的先验调整系数（0.0~1.5）。
    1.0 = 无调整；>1.0 = 加权增强；<1.0 = 降低权重。
    用于在 check10d 时调整维度权重。
    """
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT dim_id, belief, hit_count, miss_count FROM dimension_beliefs")
        rows = cur.fetchall()
    finally:
        conn.close()

    adjustments = {}
    for dim_id, belief, hit, miss in rows:
        # 信念 >0.5：该维度历史判断质量好 → 加权
        # 信念 <0.5：该维度历史判断质量差 → 降权
        # map [0,1] → [0.7, 1.3]
        if hit + miss < 3:
            adjustments[dim_id] = 1.0  # 样本不足，不调整
        else:
            adjustments[dim_id] = 0.7 + 0.6 * belief  # 0.7~1.3
    return adjustments


# ── 查历史因果链 ──────────────────────────────────────────────────────────

def get_recent_chains(limit: int = 5) -> List[Dict]:
    """返回最近的因果链记录（供调试/回顾）"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT chain_id, ts, task_text, dimensions, outcome, corrected FROM causal_chain ORDER BY ts DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for chain_id, ts, task_text, dims_json, outcome, corrected in rows:
        dims_data = json.loads(dims_json) if dims_json else {}
        result.append({
            "chain_id": chain_id,
            "ts": ts,
            "task": (task_text or "")[:100],
            "dimensions": dims_data.get("dims", []),
            "outcome": outcome,
            "corrected": bool(corrected),
        })
    return result


def get_belief_summary() -> Dict[str, Dict]:
    """返回各维度信念概览"""
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT dim_id, belief, hit_count, miss_count FROM dimension_beliefs")
        rows = cur.fetchall()
    finally:
        conn.close()

    return {
        dim_id: {
            "belief": round(belief, 4),
            "hit": hit,
            "miss": miss,
            "total": hit + miss,
            "accuracy": round(hit / (hit + miss), 3) if (hit + miss) > 0 else None,
        }
        for dim_id, belief, hit, miss in rows
    }





       