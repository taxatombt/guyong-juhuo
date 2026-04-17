#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_verdicts.py — 批量种子 verdict 导入

使用方式：
    python judgment/seed_verdicts.py --all
    python judgment/seed_verdicts.py --auto
    python judgment/seed_verdicts.py --retro
"""

import json, sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "judgment_data" / "juhuo_judgment.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Ground Truth 来源
MANUAL_VERDICTS = [
    ("seed_b001", "要不要辞职创业？", 1, "高风险决策，谨慎评估是对的"),
    ("seed_b002", "朋友借5万要不要借？", 1, "关系和还款能力权衡正确"),
    ("seed_b003", "买郊区大房子还是市区小房子？", 1, "取决于生活阶段判断合理"),
    ("seed_b004", "要不要移民加拿大？", 0, "未充分权衡政策风险"),
    ("seed_b005", "周末加班还是陪家人？", 1, "根据紧急程度判断正确"),
    ("seed_b006", "要不要读研究生？", 1, "职业规划权衡合理"),
    ("seed_b007", "要不要投资数字货币？", 1, "高风险投资判断正确"),
    ("seed_b008", "要不要换城市工作？", 1, "机会和生活权衡合理"),
    ("seed_b009", "要不要接受降薪但有股权的offer？", 1, "评估股权价值合理"),
    ("seed_b010", "要不要提前还房贷？", 1, "比较贷款利率判断正确"),
    ("seed_b011", "要不要和女朋友分手？", 0, "感情判断过于理性"),
    ("seed_b012", "朋友得罪了我要不要原谅？", 1, "动机和长期关系价值权衡合理"),
    ("seed_b013", "要不要让孩子学编程？", 1, "评估兴趣和趋势合理"),
    ("seed_b014", "要不要辞职休息一段时间？", 1, "身心健康评估合理"),
    ("seed_b015", "要不要把父母接来同住？", 1, "代际关系权衡合理"),
    ("seed_b016", "要不要考公务员？", 0, "未充分考虑个人价值观"),
    ("seed_b017", "要不要买商业保险？", 1, "风险敞口评估合理"),
    ("seed_b018", "要不要现在买房？", 0, "未充分考虑房价下行风险"),
    ("seed_b019", "要不要all in 一只股票？", 1, "分散风险判断正确"),
    ("seed_b020", "要不要开始健身？", 1, "长期收益判断正确"),
    ("seed_b021", "要不要断舍离精简生活？", 1, "适合焦虑人群判断合理"),
    ("seed_b022", "领养一只猫", 1, "评估生活方式合理"),
    ("seed_b023", "做决定时是否过于依赖直觉？", 0, "当时应该多收集数据再判断"),
    ("seed_b024", "换工作时是否考虑了机会成本？", 1, "充分权衡了新旧工作的差异"),
    ("seed_b025", "朋友冲突时是否处理得当？", 0, "当时情绪化反应过度"),
    ("seed_b026", "重大投资时是否分散了风险？", 1, "做好了仓位控制"),
    ("seed_b027", "家庭重大决策时是否和家人充分沟通？", 0, "独断了，没有征求家人意见"),
]

RETROSPECTIVE_CASES = [
    ("retro_01", "做决定时是否过于依赖直觉？", 0, "当时应该多收集数据再判断"),
    ("retro_02", "换工作时是否考虑了机会成本？", 1, "充分权衡了新旧工作的差异"),
    ("retro_03", "朋友冲突时是否处理得当？", 0, "当时情绪化反应过度"),
    ("retro_04", "重大投资时是否分散了风险？", 1, "做好了仓位控制"),
    ("retro_05", "家庭重大决策时是否和家人充分沟通？", 0, "独断了，没有征求家人意见"),
]


def _conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_tables():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS verdict_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT NOT NULL,
                task_text TEXT,
                correct INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_verdict_chain ON verdict_outcomes(chain_id);
        """)


def seed_verdicts(verdicts: List[Tuple], label: str) -> int:
    init_tables()
    imported = 0
    now = datetime.now().isoformat()
    with _conn() as c:
        for chain_id, task_text, correct, notes in verdicts:
            existing = c.execute(
                "SELECT id FROM verdict_outcomes WHERE chain_id = ?", (chain_id,)
            ).fetchone()
            if existing:
                continue
            c.execute(
                "INSERT INTO verdict_outcomes (chain_id, task_text, correct, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                (chain_id, task_text[:500], correct, notes[:200], now)
            )
            imported += 1
        c.commit()
    return imported


def get_stats() -> Dict:
    init_tables()
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM verdict_outcomes").fetchone()[0]
        correct = c.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=1").fetchone()[0]
        wrong = c.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=0").fetchone()[0]
        accuracy = correct / total if total > 0 else 0.0
        return {
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "accuracy": accuracy,
            "ready_for_evolution": total >= 5,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed verdict ground truth data")
    parser.add_argument("--auto", action="store_true", help="手动标记 verdicts")
    parser.add_argument("--retro", action="store_true", help="回顾性 verdicts")
    parser.add_argument("--all", action="store_true", help="导入全部")
    args = parser.parse_args()

    stats_before = get_stats()
    print(f"[seed_verdicts] 当前: {stats_before['total']} verdict, 准确率 {stats_before['accuracy']:.1%}")

    if args.auto or args.all:
        n = seed_verdicts(MANUAL_VERDICTS, "手动")
        print(f"  [手动] 导入 {n} 条")

    if args.retro or args.all:
        n = seed_verdicts(RETROSPECTIVE_CASES, "回顾")
        print(f"  [回顾] 导入 {n} 条")

    if not (args.auto or args.retro or args.all):
        n1 = seed_verdicts(MANUAL_VERDICTS, "手动")
        n2 = seed_verdicts(RETROSPECTIVE_CASES, "回顾")
        print(f"  [默认全部] 导入 {n1+n2} 条")

    stats_after = get_stats()
    print(f"[seed_verdicts] 更新后: {stats_after['total']} verdict, 准确率 {stats_after['accuracy']:.1%}")
    print(f"  进化就绪: {'✅' if stats_after['ready_for_evolution'] else '❌'}")


if __name__ == "__main__":
    main()
