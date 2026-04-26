#!/usr/bin/env python3
"""
_migrate_skill_quality.py — ZeusHammer SkillQuality 评估体系落地

从 ZeusHammer skill_learner.py 学到的:
1. experiences 表增加 quality tracking 字段
2. 实现 SkillLearner._calculate_score 评分算法
3. 实现 should_retire 逻辑（30天未用 or score < 20）
4. 实现 update_experience_quality — 每次执行后更新质量数据

ZeusHammer 评分公式:
  - 成功率得分 (0-40): success_rate * 40
  - 速度得分 (0-30): max(0, 30 - avg_duration_ms/1000 * 30)
  - 使用频率得分 (0-20): min(20, usage_count * 2)
  - 复杂度得分 (0-10): (6 - complexity) * 2
  - Total: 0-100
"""

import sqlite3
import time
import json
from pathlib import Path

DB_PATH = Path("E:/juhuo/data/juhuo.db")

SCHEMA_ALTERS = [
    # Quality tracking fields
    ("usage_count", "INTEGER DEFAULT 0"),
    ("success_count", "INTEGER DEFAULT 0"),
    ("avg_duration_ms", "REAL DEFAULT 0.0"),
    ("last_used", "REAL DEFAULT 0"),  # unix timestamp
    ("quality_score", "REAL DEFAULT 50.0"),  # 0-100 composite
    ("should_retire", "INTEGER DEFAULT 0"),  # boolean flag
    ("complexity", "INTEGER DEFAULT 1"),  # 1-5
]

EXPIRY_DAYS = 30
RETIRE_THRESHOLD = 20.0
RETIRE_DAYS_INACTIVE = 30


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def schema_has_column(conn, table, column):
    c = conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name=?",
        (table, column)
    )
    return conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name=?",
        (table, column)
    ).fetchone()[0] > 0


def migrate_schema():
    """添加 quality tracking 字段"""
    conn = get_db()
    added = []
    for col_name, col_def in SCHEMA_ALTERS:
        if not schema_has_column(conn, "experiences", col_name):
            conn.execute(f"ALTER TABLE experiences ADD COLUMN {col_name} {col_def}")
            added.append(col_name)
            print(f"  + {col_name} {col_def}")
        else:
            print(f"  = {col_name} (exists)")
    conn.commit()
    conn.close()
    print(f"\nSchema migration: {len(added)} columns added")
    return added


def calculate_score(success_rate, avg_duration_ms, usage_count, complexity):
    """
    ZeusHammer SkillLearner._calculate_score 实现:
    - 成功率得分 (0-40): success_rate * 40
    - 速度得分 (0-30): max(0, 30 - avg_duration_ms/1000 * 30)
    - 使用频率得分 (0-20): min(20, usage_count * 2)
    - 复杂度得分 (0-10): (6 - complexity) * 2
    - Total: 0-100
    """
    success_score = success_rate * 40
    speed_score = max(0.0, 30.0 - (avg_duration_ms / 1000.0) * 30.0)
    usage_score = min(20.0, usage_count * 2.0)
    complexity_score = (6 - complexity) * 2.0
    return round(success_score + speed_score + usage_score + complexity_score, 2)


def update_experience_quality(exp_id, duration_ms, success, conn=None):
    """
    每次 experience 被命中执行后调用，更新质量数据。
    
    来自 ZeusHammer SkillLearner.evaluate_skill 逻辑:
    1. 更新 usage_count
    2. 更新 success_count
    3. 更新 avg_duration_ms (滑动平均)
    4. 更新 last_used
    5. 重新计算 quality_score
    6. 检查 should_retire
    """
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True
    
    row = conn.execute(
        "SELECT usage_count, success_count, avg_duration_ms, quality_score, last_used, complexity FROM experiences WHERE id=?",
        (exp_id,)
    ).fetchone()
    
    if row is None:
        if close_conn:
            conn.close()
        return
    
    usage_count = row["usage_count"]
    success_count = row["success_count"]
    avg_duration_ms = row["avg_duration_ms"]
    last_used = row["last_used"]
    complexity = row["complexity"]
    
    # 更新计数器
    usage_count += 1
    if success:
        success_count += 1
    
    # 更新平均耗时（滑动平均）
    avg_duration_ms = ((avg_duration_ms * (usage_count - 1)) + duration_ms) / usage_count
    
    # 更新最后使用时间
    last_used = time.time()
    
    # 计算新评分
    success_rate = success_count / usage_count if usage_count > 0 else 0.0
    quality_score = calculate_score(success_rate, avg_duration_ms, usage_count, complexity)
    
    # 检查是否应该淘汰
    should_retire = 0
    if quality_score < RETIRE_THRESHOLD:
        should_retire = 1
    else:
        inactive_days = (time.time() - last_used) / 86400
        if inactive_days > RETIRE_DAYS_INACTIVE:
            should_retire = 1
    
    conn.execute("""
        UPDATE experiences SET
            usage_count = ?,
            success_count = ?,
            avg_duration_ms = ?,
            last_used = ?,
            quality_score = ?,
            should_retire = ?
        WHERE id = ?
    """, (usage_count, success_count, avg_duration_ms, last_used, quality_score, should_retire, exp_id))
    
    if close_conn:
        conn.commit()
        conn.close()
    
    return quality_score


def retire_low_quality(conn=None):
    """
    ZeusHammer SkillLearner.should_retire_skill 实现:
    - score < 20 → 淘汰
    - 30天未使用 → 淘汰
    """
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True
    
    now = time.time()
    threshold_ts = now - (RETIRE_DAYS_INACTIVE * 86400)
    
    # 淘汰标准：score < 20 或 30天未用
    rows = conn.execute("""
        SELECT id, quality_score, last_used FROM experiences
        WHERE should_retire = 0
        AND (quality_score < ? OR (last_used > 0 AND last_used < ?))
    """, (RETIRE_THRESHOLD, threshold_ts)).fetchall()
    
    retired = []
    for row in rows:
        conn.execute("UPDATE experiences SET should_retire=1 WHERE id=?", (row["id"],))
        retired.append(row["id"])
    
    if close_conn:
        conn.commit()
        conn.close()
    
    return retired


def print_quality_report(conn=None):
    """打印 experiences 质量报告"""
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True
    
    rows = conn.execute("""
        SELECT id, task_text, quality_score, usage_count, success_count,
               avg_duration_ms, should_retire, last_used
        FROM experiences
        ORDER BY quality_score ASC
    """).fetchall()
    
    print(f"\n{'='*70}")
    print(f"ZeusHammer SkillQuality Report — experiences")
    print(f"{'='*70}")
    print(f"{'ID':>4} {'Score':>6} {'Uses':>5} {'Succ%':>6} {'AvgMs':>8} {'Retire':>6}  Task")
    print(f"{'-'*70}")
    
    for row in rows:
        succ_rate = (row["success_count"] / row["usage_count"] * 100) if row["usage_count"] > 0 else 0
        retire_str = "YES" if row["should_retire"] else ""
        task = (row["task_text"] or "")[:35]
        print(f"{row['id']:>4} {row['quality_score']:>6.1f} {row['usage_count']:>5} {succ_rate:>5.0f}% {row['avg_duration_ms']:>8.0f} {retire_str:>6}  {task}")
    
    total = len(rows)
    retire_count = sum(1 for r in rows if r["should_retire"])
    print(f"{'-'*70}")
    print(f"Total: {total} experiences | {retire_count} marked for retirement")
    
    if close_conn:
        conn.close()


if __name__ == "__main__":
    print("ZeusHammer SkillQuality migration")
    print("=" * 50)
    
    # 1. Migration
    print("\n[1] Schema migration")
    added = migrate_schema()
    
    # 2. Initial quality score backfill (for existing experiences)
    print("\n[2] Backfill quality scores")
    conn = get_db()
    existing = conn.execute("SELECT id, outcome_score FROM experiences WHERE quality_score = 50.0").fetchall()
    if existing:
        for row in existing:
            # Use outcome_score as proxy for success_rate
            success = 1 if (row["outcome_score"] or 0) >= 0.6 else 0
            update_experience_quality(row["id"], 0, success, conn)
        print(f"  Backfilled {len(existing)} experiences")
    else:
        print("  No experiences need backfill")
    conn.commit()
    
    # 3. Run retirement check
    print("\n[3] Retirement check")
    retired = retire_low_quality()
    print(f"  {len(retired)} experiences marked for retirement")
    
    # 4. Print report
    print_quality_report()
