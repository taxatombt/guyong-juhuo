#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment_db.py — Juhuo SQLite数据层

P2改进: 把judgment_data/的JSON/JSONL迁移到SQLite

核心表:
- judgments: 每次判断快照
- verdict_outcomes: 判断结果反馈
- dimension_stats: 维度准确率统计
"""

import sqlite3, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager
from threading import Lock

_JD = Path(__file__).parent.parent / "data" / "judgment_data"
_DB = _JD / "juhuo_judgment.db"
_JD.mkdir(parents=True, exist_ok=True)

_lock = Lock()


@contextmanager
def get_conn():
    with _lock:
        conn = sqlite3.connect(_DB, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def init_db():
    """初始化数据库表"""
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS judgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT UNIQUE NOT NULL,
                task_text TEXT NOT NULL,
                dimensions TEXT NOT NULL,
                weights TEXT NOT NULL,
                answers TEXT,
                result TEXT,
                complexity TEXT DEFAULT 'normal',
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_judgments_chain ON judgments(chain_id);
            CREATE INDEX IF NOT EXISTS idx_judgments_created ON judgments(created_at);
            
            CREATE TABLE IF NOT EXISTS verdict_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT NOT NULL,
                task_text TEXT,
                correct INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_verdict_chain ON verdict_outcomes(chain_id);
            
            CREATE TABLE IF NOT EXISTS dimension_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dimension TEXT UNIQUE NOT NULL,
                correct_count INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.5,
                last_updated TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS fitness_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT,
                task_text TEXT,
                correct INTEGER NOT NULL,
                dimension_changes TEXT,
                created_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_fitness_created ON fitness_records(created_at);
        """)
        c.commit()


init_db()


# ── 写入Judgment ────────────────────────────────────────────────────
def save_judgment(
    chain_id: str,
    task_text: str,
    dimensions: List[str],
    weights: Dict[str, float],
    answers: Dict = None,
    result: Dict = None,
    complexity: str = "normal",
) -> bool:
    """保存判断快照"""
    now = datetime.now().isoformat()
    try:
        with get_conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO judgments 
                (chain_id, task_text, dimensions, weights, answers, result, complexity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chain_id, task_text,
                json.dumps(dimensions), json.dumps(weights),
                json.dumps(answers or {}), json.dumps(result or {}),
                complexity, now,
            ))
            c.commit()
        return True
    except Exception as e:
        print(f"[judgment_db] save_judgment error: {e}")
        return False


# ── 写入Verdict ────────────────────────────────────────────────────
def save_verdict(chain_id: str, task_text: str, correct: bool, notes: str = "") -> bool:
    """保存判断结果反馈"""
    now = datetime.now().isoformat()
    try:
        with get_conn() as c:
            c.execute("""
                INSERT INTO verdict_outcomes (chain_id, task_text, correct, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (chain_id, task_text or "", 1 if correct else 0, notes[:200], now))
            c.commit()
        return True
    except Exception as e:
        print(f"[judgment_db] save_verdict error: {e}")
        return False


# ── 更新维度统计 ────────────────────────────────────────────────────
def update_dimension_stats(dimension: str, correct: bool) -> bool:
    """更新维度准确率"""
    now = datetime.now().isoformat()
    try:
        with get_conn() as c:
            row = c.execute(
                "SELECT correct_count, total_count FROM dimension_stats WHERE dimension=?",
                (dimension,)
            ).fetchone()
            
            if row:
                new_correct = row["correct_count"] + (1 if correct else 0)
                new_total = row["total_count"] + 1
                new_acc = new_correct / new_total if new_total > 0 else 0.5
                c.execute("""
                    UPDATE dimension_stats SET correct_count=?, total_count=?, accuracy=?, last_updated=?
                    WHERE dimension=?
                """, (new_correct, new_total, new_acc, now, dimension))
            else:
                c.execute("""
                    INSERT INTO dimension_stats (dimension, correct_count, total_count, accuracy, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (dimension, 1 if correct else 0, 1, 1.0 if correct else 0.0, now))
            
            c.commit()
        return True
    except Exception as e:
        print(f"[judgment_db] update_dimension_stats error: {e}")
        return False


# ── 查询 ────────────────────────────────────────────────────────────
def get_judgment(chain_id: str) -> Optional[Dict]:
    """获取判断快照"""
    with get_conn() as c:
        row = c.execute("SELECT * FROM judgments WHERE chain_id=?", (chain_id,)).fetchone()
        return dict(row) if row else None


def get_recent_judgments(limit: int = 10) -> List[Dict]:
    """获取最近的判断"""
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM judgments ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_dimension_stats() -> Dict[str, Dict]:
    """获取所有维度统计"""
    with get_conn() as c:
        rows = c.execute("SELECT * FROM dimension_stats").fetchall()
        return {r["dimension"]: dict(r) for r in rows}


def get_overall_accuracy() -> float:
    """获取整体准确率"""
    with get_conn() as c:
        row = c.execute("""
            SELECT SUM(correct_count) as total_correct, SUM(total_count) as total_all
            FROM dimension_stats
        """).fetchone()
        if row and row["total_all"] and row["total_all"] > 0:
            return row["total_correct"] / row["total_all"]
    return 0.5


def get_verdict_history(limit: int = 20) -> List[Dict]:
    """获取verdict历史"""
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM verdict_outcomes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── 统计 ───────────────────────────────────────────────────────────
def get_stats() -> Dict:
    """获取整体统计"""
    with get_conn() as c:
        judgment_count = c.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
        verdict_count = c.execute("SELECT COUNT(*) FROM verdict_outcomes").fetchone()[0]
        correct_count = c.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=1").fetchone()[0]
        
        return {
            "total_judgments": judgment_count,
            "total_verdicts": verdict_count,
            "correct_count": correct_count,
            "overall_accuracy": correct_count / verdict_count if verdict_count > 0 else 0.5,
            "dimension_count": c.execute("SELECT COUNT(*) FROM dimension_stats").fetchone()[0],
        }


# ── 迁移旧JSON ─────────────────────────────────────────────────────
def migrate_from_json():
    """从旧JSON文件迁移数据（一次性）"""
    # fitness_evolution.json → dimension_stats
    ev_file = _JD / "fitness_evolution.json"
    if ev_file.exists():
        try:
            data = json.loads(ev_file.read_text(encoding="utf-8"))
            for dim, stats in data.get("accuracy", {}).items():
                if isinstance(stats, dict):
                    update_dimension_stats(dim, stats.get("accuracy", 0.5) >= 0.5)
            print(f"[judgment_db] migrated from {ev_file}")
        except Exception as e:
            print(f"[judgment_db] migrate error: {e}")
