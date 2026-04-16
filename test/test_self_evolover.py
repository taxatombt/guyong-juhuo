#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_self_evolover.py — Self-Evolver 闭环测试
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def init_test_db():
    """初始化测试数据库"""
    from judgment.judgment_db import get_conn
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS judgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT UNIQUE,
                task_text TEXT,
                dimensions TEXT,
                weights TEXT,
                answers TEXT,
                result TEXT,
                complexity TEXT DEFAULT 'normal',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS verdict_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT,
                task_text TEXT,
                correct INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS dimension_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dimension TEXT UNIQUE,
                correct_count INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.5,
                weight REAL DEFAULT 0.5,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    print("[DB] 测试数据库初始化完成")


def test_sync_to_self_model():
    """测试1: Hook数据同步到self_model"""
    from judgment.self_evolover import sync_to_self_model
    from judgment.judgment_db import get_conn
    from datetime import datetime
    
    chain_id = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO judgments (chain_id, task_text, dimensions, weights, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (chain_id, "测试任务", '["安全性","效率"]', '{"安全性":0.6,"效率":0.4}', datetime.now().isoformat()))
        conn.execute("""
            INSERT OR REPLACE INTO verdict_outcomes (chain_id, task_text, correct, created_at)
            VALUES (?, ?, ?, ?)
        """, (chain_id, "测试任务", 0, datetime.now().isoformat()))
        conn.commit()
    
    result = sync_to_self_model(chain_id)
    print(f"[测试1] 同步结果: {result}")
    return True


def test_evolution_trigger():
    """测试2: 检查触发条件"""
    from judgment.self_evolover import check_trigger
    
    result = check_trigger()
    print(f"[测试2] 触发检查: {result}")
    assert "triggered" in result
    return True


def test_rule_training():
    """测试3: 规则训练"""
    from judgment.self_evolover import get_cases, compute_new_weights
    
    cases = get_cases()
    print(f"[测试3] 获取案例: {len(cases)} 条")
    
    if cases:
        weights = compute_new_weights(cases)
        print(f"[测试3] 新权重: {weights}")
    
    return True


def test_evolution_cycle():
    """测试4: 完整闭环"""
    from judgment.self_evolover import run_evolution_cycle
    
    result = run_evolution_cycle()
    print(f"[测试4] 闭环结果: {result['status']}")
    if result.get("triggered"):
        print(f"  触发原因: {result['trigger'].get('reason')}")
        print(f"  优胜者: {result.get('winner')}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Self-Evolver 闭环测试")
    print("=" * 60)
    
    init_test_db()
    
    tests = [
        ("Hook数据同步", test_sync_to_self_model),
        ("触发条件检查", test_evolution_trigger),
        ("规则训练", test_rule_training),
        ("完整闭环", test_evolution_cycle),
    ]
    
    passed = 0
    for name, func in tests:
        print(f"\n>>> 测试: {name}")
        try:
            func()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"结果: {passed}/{len(tests)} 通过")
    print("=" * 60)