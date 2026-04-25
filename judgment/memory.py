# judgment/memory.py
# Shim: 历史 API，映射到独立 decisions.db（web/app.py + evolver 使用）
# Migration: 2026-04-25（之前 missing，导致 web/app.py ImportError）
from pathlib import Path
import sqlite3, threading, os

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "decisions"
_MEM_DIR = Path(__file__).resolve().parents[1] / "data" / "decisions"

# 兼容：MEMORY_DIR = 目录路径，init() 创建 decisions.db
MEMORY_DIR = _MEM_DIR

_lock = threading.Lock()

def init():
    """初始化 decisions.db（thread-safe）"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _DATA_DIR / "decisions.db"
    with _lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT, complexity TEXT DEFAULT 'auto',
                checked TEXT, skipped TEXT, profile TEXT,
                user_decision TEXT, feedback TEXT, rating INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

def log_decision(task, complexity="auto", checked="", skipped="", profile="",
                 user_decision="", feedback="", rating=0):
    """记录一次判断决策（thread-safe）"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _DATA_DIR / "decisions.db"
    with _lock:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.execute("""
            INSERT INTO decisions (task, complexity, checked, skipped, profile,
                                   user_decision, feedback, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (task, complexity, checked, skipped, profile,
              user_decision, feedback, rating))
        conn.commit()
        conn.close()

def get_recent_decisions(limit=20):
    """返回近期判断列表（dict 列表）"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _DATA_DIR / "decisions.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, task, complexity, checked, skipped, profile,
               user_decision, feedback, rating, created_at
        FROM decisions ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# evolver 用（别名）
def get_decisions(limit=100):
    return get_recent_decisions(limit)

__all__ = ['MEMORY_DIR', 'init', 'log_decision', 'get_recent_decisions', 'get_decisions']
