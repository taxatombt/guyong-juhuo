#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sqlite_schema.py — SQLite 数据分层 Schema

三张核心表：
  1. lessons       — 教训记录（从 evolver/self_lessons.jsonl 迁移）
  2. snapshots     — 快照记录（从 checkpoints/ 迁移）
  3. health_metrics — 健康指标（从 metrics/ 迁移）

设计原则：
  - WAL 模式，读写分离
  - crash recovery（SQLite WAL 自动）
  - 迁移后保留原始 JSON 文件（备份为 .bak）

使用方式：
    from evolver.sqlite_schema import init_db, get_db

    db = get_db()
    db.execute("INSERT INTO lessons (...)", ...)
    db.commit()
"""

import sqlite3
import json
import shutil
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_FILE = DATA_DIR / "evolutions" / "juhuo.db"


# ─── Schema ─────────────────────────────────────────────────────────────────

SCHEMA = """
-- 教训表：从 evolver/self_lessons.jsonl 迁移
CREATE TABLE IF NOT EXISTS lessons (
    id          TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    source      TEXT,
    pattern     TEXT,  -- JSON
    tags        TEXT,  -- JSON list
    outcome     TEXT,
    created_at  REAL DEFAULT (unixepoch())
);

-- 快照表：从 data/checkpoints/ 迁移
CREATE TABLE IF NOT EXISTS snapshots (
    id          TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    agent_state TEXT,  -- JSON
    metrics     TEXT,  -- JSON
    checkpoint_path TEXT,
    created_at  REAL DEFAULT (unixepoch())
);

-- 健康指标表：从 data/metrics/ 迁移
CREATE TABLE IF NOT EXISTS health_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    metric_type TEXT NOT NULL,
    value       REAL,
    tags        TEXT,  -- JSON
    created_at  REAL DEFAULT (unixepoch())
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_lessons_timestamp ON lessons(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_lessons_source   ON lessons(source);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_type ON health_metrics(metric_type);
"""


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """创建 WAL 模式连接。"""
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """上下文管理器：自动提交/回滚。"""
    path = db_path or DB_FILE
    conn = _get_conn(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """初始化数据库（创建表）。"""
    path = db_path or DB_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = _get_conn(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return _get_conn(path)


def backup_json(src: Path, suffix: str = ".bak") -> None:
    """备份 JSON 文件为 .bak。"""
    if src.exists():
        shutil.copy2(src, src.with_suffix(src.suffix + suffix))
