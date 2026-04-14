#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
causal_memory_sqlite.py — causal_memory SQLite 后端

提供 SQLite 版本的 causal_memory 核心操作。
record_event / load_all_events / find_similar_events / check_and_trigger_self_model_update
全部使用 SQLite，性能大幅提升。

数据文件：
    {PROJECT_ROOT}/data/causal_memory/events.db — SQLite 数据库
"""
import json, math, os, sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import difflib

DB_PATH = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"
SIMILARITY_THRESHOLD = 0.65
DECAY_HALF_LIFE = 365
PERSONAL_CAUSAL_BONUS = 0.5
PATTERN_THRESHOLD = 2

def _conn():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def _next_event_id(conn) -> int:
    row = conn.execute("SELECT MAX(event_id) FROM events").fetchone()
    return (row[0] or 0) + 1

def _next_link_id(conn) -> int:
    row = conn.execute("SELECT MAX(link_id) FROM causal_links").fetchone()
    return (row[0] or 0) + 1

def _task_similarity(a: str, b: str) -> float:
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def init():
    c = _conn()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY,
            timestamp TEXT,
            category TEXT,
            description TEXT,
            task TEXT,
            why_i_think_so TEXT,
            outcome TEXT,
            dimensions TEXT,
            judgment_summary TEXT,
            tags TEXT,
            chain_id TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS causal_links (
            link_id INTEGER PRIMARY KEY,
            from_event_id INTEGER,
            to_event_id INTEGER,
            relation TEXT,
            confidence REAL,
            timestamp TEXT,
            inferred INTEGER,
            evolution_type TEXT,
            quality TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_events_category ON events(category)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_events_task ON events(task)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_events_outcome ON events(outcome)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_links_from ON causal_links(from_event_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_links_to ON causal_links(to_event_id)")
        c.commit()
    finally: c.close()

# ── record_event (SQLite版) ────────────────────────────────────────────────

def record_event(
    event_type: str,
    description: str,
    what_happened: str,
    why_i_think_so: str,
    outcome: str = None,
    judgment_summary: dict = None,
    tags: List[str] = None,
    chain_id: str = None,
) -> int:
    """SQLite版 record_event，供 causal_memory.record_event 调用"""
    init()
    conn = _conn()
    try:
        event_id = _next_event_id(conn)
        dims = judgment_summary.get("dims", []) if judgment_summary else []
        conn.execute("""INSERT INTO events
            (event_id,timestamp,category,description,task,why_i_think_so,outcome,dimensions,judgment_summary,tags,chain_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, datetime.now().isoformat(), event_type, description, what_happened,
             why_i_think_so, outcome, json.dumps(dims, ensure_ascii=False),
             json.dumps(judgment_summary or {}, ensure_ascii=False),
             json.dumps(tags or [], ensure_ascii=False), chain_id))
        conn.commit()
        return event_id
    finally: conn.close()

# ── load_all_events ─────────────────────────────────────────────────────────

def load_all_events() -> List[dict]:
    """从 SQLite 加载所有事件"""
    conn = _conn()
    try:
        rows = conn.execute("SELECT event_id,timestamp,category,description,task,why_i_think_so,outcome,dimensions,judgment_summary,tags,chain_id FROM events ORDER BY event_id DESC").fetchall()
        events = []
        for r in rows:
            dims_raw = r[7]
            events.append({
                "event_id": r[0],
                "timestamp": r[1],
                "category": r[2],
                "description": r[3],
                "task": r[4],
                "why_i_think_so": r[5],
                "outcome": r[6],
                "dimensions": json.loads(dims_raw) if dims_raw else [],
                "judgment_summary": json.loads(r[8]) if r[8] else {},
                "tags": json.loads(r[9]) if r[9] else [],
                "chain_id": r[10],
            })
        return events
    finally: conn.close()

# ── find_similar_events ─────────────────────────────────────────────────────

def find_similar_events(task: str, max_results: int = 3) -> List[dict]:
    """找相似任务事件"""
    events = load_all_events()
    if not events: return []
    scored = [(e, _task_similarity(task, e.get("task", ""))) for e in events]
    scored.sort(key=lambda x: -x[1])
    return [e for e, s in scored[:max_results] if s >= SIMILARITY_THRESHOLD]

# ── check_and_trigger_self_model_update ────────────────────────────────────

def check_and_trigger_self_model_update(task: str, dimensions: List[str], correct: bool, pattern_key: str = None) -> dict:
    """SQLite版 pattern 检测 + self_model 触发"""
    import hashlib
    events = load_all_events()
    dims_key = "|".join(sorted(dimensions)) if dimensions else "none"
    if pattern_key is None:
        task_hash = hashlib.md5(task.encode("utf-8")).hexdigest()[:8]
        pattern_key = f"{dims_key}:{task_hash}"

    similar = [
        e for e in events
        if e.get("category") == "judgment_verdict"
        and e.get("outcome") is not None
        and "|".join(sorted(e.get("dimensions", []))) == dims_key
        and _task_similarity(task, e.get("task", "")) >= SIMILARITY_THRESHOLD
    ]
    count = len(similar)

    if count >= PATTERN_THRESHOLD:
        wrong_dims = [d for d in dimensions if d] if not correct else []
        feedback_event = {
            "source": "causal_memory_sqlite",
            "pattern_key": pattern_key,
            "feedback_type": "judgment_repeated_mistake" if not correct else "judgment_repeated_success",
            "task_sample": task[:200],
            "dimensions": dimensions,
            "wrong_dimensions": wrong_dims,
            "correct": correct,
            "occurrence_count": count,
        }
        global _lazy_update
        if "_lazy_update" not in globals() or _lazy_update is None:
            try:
                from self_model.self_model import update_from_feedback
                globals()["_lazy_update"] = update_from_feedback
            except Exception:
                globals()["_lazy_update"] = False
        updater = globals().get("_lazy_update")
        if updater:
            try:
                result = updater(feedback_event)
                return {"triggered": True, "count": count, "threshold": PATTERN_THRESHOLD, "result": result}
            except Exception as e:
                return {"triggered": True, "count": count, "threshold": PATTERN_THRESHOLD, "error": str(e)}
       