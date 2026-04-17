#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_memory_system.py - 4类记忆系统测试

运行: python test/test_memory_system.py
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用临时目录进行测试
TEST_DIR = Path(tempfile.mkdtemp())


def setup_test_env():
    """设置测试环境"""
    import memory_system.memory_types as mt
    mt.MEMORY_DIR = TEST_DIR / "memories"
    mt.MEMORY_DIR.mkdir(exist_ok=True)
    mt.USER_FILE = mt.MEMORY_DIR / "user_memories.jsonl"
    mt.FEEDBACK_FILE = mt.MEMORY_DIR / "feedback_memories.jsonl"
    mt.PROJECT_FILE = mt.MEMORY_DIR / "project_memories.jsonl"
    mt.REFERENCE_FILE = mt.MEMORY_DIR / "reference_memories.jsonl"
    print(f"[Setup] Test dir: {TEST_DIR}")


def test_save_and_recall():
    """Test 1: Save and recall user memory"""
    from memory_system import save_user_memory, recall_memories, MemoryType
    
    memory_id = save_user_memory(
        "User is data scientist, prefers brief answers",
        scope="private"
    )
    assert memory_id is not None, "Memory ID should not be empty"
    print(f"[Test 1-1] [PASS] Save user memory: {memory_id}")
    
    memories = recall_memories("data scientist")
    assert len(memories) > 0, "Should recall relevant memory"
    assert memories[0]["content"] == "User is data scientist, prefers brief answers"
    print(f"[Test 1-2] [PASS] Recall success")
    
    return True


def test_feedback_memory():
    """Test 2: Save and recall feedback memory"""
    from memory_system import save_feedback_memory, recall_memories, MemoryType
    
    memory_id = save_feedback_memory(
        content="Check config file first when issue occurs",
        outcome="guidance",
        trigger_context="Config file issue"
    )
    assert memory_id is not None
    print(f"[Test 2-1] [PASS] Save feedback memory: {memory_id}")
    
    memories = recall_memories("Config file", memory_types=[MemoryType.FEEDBACK])
    assert len(memories) > 0
    assert memories[0]["outcome"] == "guidance"
    print(f"[Test 2-2] [PASS] Feedback recall success")
    
    return True


def test_project_memory():
    """Test 3: Save and recall project memory"""
    from memory_system import save_project_memory, recall_memories, MemoryType
    
    memory_id = save_project_memory(
        content="Refactoring judgment engine, expected next week",
        project_id="judgment-engine-v2",
        status="active"
    )
    assert memory_id is not None, f"memory_id is None"
    print(f"[Test 3-1] [PASS] Save project memory: {memory_id}")
    
    memories = recall_memories("judgment engine", memory_types=[MemoryType.PROJECT])
    assert len(memories) > 0, f"No memories recalled, expected at least 1"
    assert "judgment" in memories[0]["content"].lower(), f"Content mismatch: {memories[0]['content']}"
    print(f"[Test 3-2] [PASS] Project recall success")
    
    return True


def test_reference_memory():
    """Test 4: Save and recall reference memory"""
    from memory_system import save_reference_memory, recall_memories, MemoryType
    
    memory_id = save_reference_memory(
        content="juhuo API docs location",
        source_system="juhuo",
        source_url="https://github.com/taxatombt/guyong-juhuo",
        content_hash="abc123"
    )
    assert memory_id is not None
    print(f"[Test 4-1] [PASS] Save reference memory: {memory_id}")
    
    memories = recall_memories("API docs", memory_types=[MemoryType.REFERENCE])
    assert len(memories) > 0
    assert memories[0]["source_system"] == "juhuo"
    print(f"[Test 4-2] [PASS] Reference recall success")
    
    return True


def test_is_worth_saving():
    """Test 5: is_worth_saving logic"""
    from memory_system import MemoryEngine
    
    engine = MemoryEngine()
    
    # Should save
    assert engine.is_worth_saving("User prefers brief answers") == True
    print("[Test 5-1] [PASS] User preference correctly identified")
    
    assert engine.is_worth_saving("User is engineer") == True
    print("[Test 5-2] [PASS] User role correctly identified")
    
    # Should NOT save (derivable) - use Chinese patterns from implementation
    assert engine.is_worth_saving("在src目录下") == False
    print("[Test 5-3] [PASS] File path correctly identified as derivable")
    
    assert engine.is_worth_saving("使用了mvc架构") == False
    print("[Test 5-4] [PASS] Architecture correctly identified as derivable")
    
    return True


def test_memory_engine():
    """Test 6: MemoryEngine unified interface"""
    from memory_system import MemoryEngine
    
    engine = MemoryEngine()
    
    user_id = engine.save("user", "Test user info")
    assert user_id is not None
    print(f"[Test 6-1] [PASS] Unified save: {user_id}")
    
    memories = engine.recall("user info", limit=3)
    assert len(memories) > 0
    print(f"[Test 6-2] [PASS] Unified recall: {len(memories)} items")
    
    stats = engine.get_stats()
    assert "user" in stats
    print(f"[Test 6-3] [PASS] Stats: {stats}")
    
    return True


def test_used_count():
    """Test 7: Used count tracking"""
    from memory_system import save_user_memory, load_memories, MemoryType, increment_used_count
    
    memory_id = save_user_memory("Test used count")
    
    memories = load_memories(MemoryType.USER)
    initial = [m for m in memories if m["id"] == memory_id][0]
    assert initial["used_count"] == 0
    
    increment_used_count(memory_id, MemoryType.USER)
    memories = load_memories(MemoryType.USER)
    after = [m for m in memories if m["id"] == memory_id][0]
    assert after["used_count"] == 1
    print("[Test 7] [PASS] Used count tracking works")
    
    return True


def test_relevance_scoring():
    """Test 8: Relevance scoring"""
    from memory_system import recall_memories, save_user_memory
    
    save_user_memory("User likes swimming")
    save_user_memory("User is software engineer")
    save_user_memory("Weather is nice today")
    
    memories = recall_memories("Software engineer work")
    assert len(memories) > 0
    
    engineer_mem = [m for m in memories if "software engineer" in m["content"]]
    assert len(engineer_mem) > 0
    print("[Test 8] [PASS] Relevance scoring works")
    
    return True


def cleanup():
    """Cleanup test files"""
    import shutil
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        print(f"[Cleanup] Removed {TEST_DIR}")


def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("Juhuo 4-Type Memory System Tests")
    print("=" * 50)
    
    setup_test_env()
    
    tests = [
        ("Save and recall user memory", test_save_and_recall),
        ("Feedback memory", test_feedback_memory),
        ("Project memory", test_project_memory),
        ("Reference memory", test_reference_memory),
        ("is_worth_saving logic", test_is_worth_saving),
        ("MemoryEngine unified interface", test_memory_engine),
        ("Used count tracking", test_used_count),
        ("Relevance scoring", test_relevance_scoring),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
                print(f"[PASS] {name}\n")
            else:
                failed += 1
                print(f"[FAIL] {name}\n")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {name}: {e}\n")
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    cleanup()
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
