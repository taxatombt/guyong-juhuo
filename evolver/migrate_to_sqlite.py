#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_to_sqlite.py — JSON → SQLite 迁移脚本

迁移范围：
  1. evolutions/self_lessons.jsonl → lessons 表
  2. data/checkpoints/*.json → snapshots 表
  3. data/metrics/*.json → health_metrics 表

使用方式：
    python migrate_to_sqlite.py        # 干跑（不写入）
    python migrate_to_sqlite.py --run  # 实际迁移
    python migrate_to_sqlite.py --verify  # 验证

备份：
    迁移前自动备份 JSON 文件为 .bak
"""

import sys
import json
import shutil
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EVOLUTIONS_DIR = DATA_DIR / "evolutions"
LESSONS_FILE = EVOLUTIONS_DIR / "self_lessons.jsonl"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
METRICS_DIR = DATA_DIR / "metrics"
DB_FILE = EVOLUTIONS_DIR / "juhuo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id          TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    source      TEXT,
    pattern     TEXT,
    tags        TEXT,
    outcome     TEXT,
    created_at  REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_lessons_timestamp ON lessons(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_lessons_source   ON lessons(source);

CREATE TABLE IF NOT EXISTS snapshots (
    id          TEXT PRIMARY KEY,
    timestamp   REAL NOT NULL,
    agent_state TEXT,
    metrics     TEXT,
    checkpoint_path TEXT,
    created_at  REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp DESC);

CREATE TABLE IF NOT EXISTS health_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    metric_type TEXT NOT NULL,
    value       REAL,
    tags        TEXT,
    created_at  REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_type ON health_metrics(metric_type);
"""


def get_conn():
    conn = sqlite3.connect(str(DB_FILE), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def migrate_lessons(conn, dry_run: bool = True) -> int:
    """迁移 self_lessons.jsonl → lessons 表。"""
    if not LESSONS_FILE.exists():
        return 0

    count = 0
    with open(LESSONS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 检查是否已存在
            cur = conn.execute("SELECT 1 FROM lessons WHERE id = ?", (record.get("id", ""),))
            if cur.fetchone():
                continue

            values = (
                record.get("id", f"lesson_{count}"),
                record.get("timestamp", 0.0),
                record.get("source", ""),
                json.dumps(record.get("pattern", {}), ensure_ascii=False),
                json.dumps(record.get("tags", []), ensure_ascii=False),
                record.get("outcome", ""),
            )
            if not dry_run:
                conn.execute(
                    "INSERT INTO lessons (id, timestamp, source, pattern, tags, outcome) VALUES (?, ?, ?, ?, ?, ?)",
                    values)
            count += 1

    if not dry_run:
        conn.commit()
    return count


def migrate_checkpoints(conn, dry_run: bool = True) -> int:
    """迁移 checkpoints/*.json → snapshots 表。"""
    if not CHECKPOINTS_DIR.exists():
        return 0

    count = 0
    for fp in CHECKPOINTS_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        cur = conn.execute("SELECT 1 FROM snapshots WHERE id = ?", (fp.stem,))
        if cur.fetchone():
            continue

        values = (
            fp.stem,
            data.get("timestamp", 0.0),
            json.dumps(data.get("agent_state", {}), ensure_ascii=False),
            json.dumps(data.get("metrics", {}), ensure_ascii=False),
            str(fp),
        )
        if not dry_run:
            conn.execute(
                "INSERT INTO snapshots (id, timestamp, agent_state, metrics, checkpoint_path) VALUES (?, ?, ?, ?, ?)",
                values)
        count += 1

    if not dry_run:
        conn.commit()
    return count


def migrate_metrics(conn, dry_run: bool = True) -> int:
    """迁移 metrics/*.json → health_metrics 表。"""
    if not METRICS_DIR.exists():
        return 0

    count = 0
    for fp in METRICS_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        # 支持多种格式：{timestamp, type, value} 或 {metrics: {...}}
        if isinstance(data, dict):
            if "metrics" in data:
                for mtype, mvalue in data["metrics"].items():
                    values = (
                        data.get("timestamp", 0.0),
                        mtype,
                        float(mvalue) if mvalue is not None else None,
                        json.dumps(data.get("tags", []), ensure_ascii=False),
                    )
                    if not dry_run:
                        conn.execute(
                            "INSERT INTO health_metrics (timestamp, metric_type, value, tags) VALUES (?, ?, ?, ?)",
                            values)
                    count += 1
            else:
                mtype = data.get("type", fp.stem)
                values = (
                    data.get("timestamp", 0.0),
                    mtype,
                    float(data.get("value", 0)) if "value" in data else None,
                    json.dumps(data.get("tags", []), ensure_ascii=False),
                )
                if not dry_run:
                    conn.execute(
                        "INSERT INTO health_metrics (timestamp, metric_type, value, tags) VALUES (?, ?, ?, ?)",
                        values)
                count += 1

    if not dry_run:
        conn.commit()
    return count


def run(dry_run: bool = True):
    """运行迁移。"""
    mode = "干跑" if dry_run else "迁移"
    print(f"=== SQLite 迁移 ({mode}) ===")
    print(f"DB 文件: {DB_FILE}")

    if dry_run:
        print("\n[干跑模式] 不写入数据库，仅报告数量")

    conn = get_conn()
    try:
        init_schema(conn)

        # 备份原始 JSON（目录不备份，只备份文件）
        if not dry_run:
            if LESSONS_FILE.exists():
                shutil.copy2(LESSONS_FILE, LESSONS_FILE.with_suffix(".jsonl.bak"))
            if METRICS_DIR.exists():
                bak_dir = METRICS_DIR.parent / (METRICS_DIR.name + ".bak")
                shutil.copytree(METRICS_DIR, bak_dir, dirs_exist_ok=True)
            if CHECKPOINTS_DIR.exists():
                bak_dir = CHECKPOINTS_DIR.parent / (CHECKPOINTS_DIR.name + ".bak")
                shutil.copytree(CHECKPOINTS_DIR, bak_dir, dirs_exist_ok=True)

        c1 = migrate_lessons(conn, dry_run)
        print(f"\nlessons:       +{c1} 条")
        c2 = migrate_checkpoints(conn, dry_run)
        print(f"snapshots:     +{c2} 条")
        c3 = migrate_metrics(conn, dry_run)
        print(f"health_metrics: +{c3} 条")
        print(f"\n总计: +{c1+c2+c3} 条")

        if not dry_run:
            print(f"\n[OK] 迁移完成，DB: {DB_FILE}")
            print(f"[备份] 原始文件已备份为 .bak")

    finally:
        conn.close()


if __name__ == "__main__":
    dry = "--run" not in sys.argv
    verify = "--verify" in sys.argv

    if verify:
        # 验证
        conn = get_conn()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM lessons")
            print(f"lessons: {cur.fetchone()[0]} 条")
            cur = conn.execute("SELECT COUNT(*) FROM snapshots")
            print(f"snapshots: {cur.fetchone()[0]} 条")
            cur = conn.execute("SELECT COUNT(*) FROM health_metrics")
            print(f"health_metrics: {cur.fetchone()[0]} 条")
        finally:
            conn.close()
    else:
        run(dry_run=dry)
