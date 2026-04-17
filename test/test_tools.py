#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_tools.py - Tools 系统测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import TOOL_REGISTRY, TOOL_STATS, list_categories, get_tool_info


def test_tool_count():
    """Test 1: 工具数量"""
    print("[Test 1] Tool Count")
    total = TOOL_STATS["total"]
    print(f"  Total tools: {total}")
    assert total >= 50, f"Should have at least 50 tools, got {total}"
    return True


def test_tool_categories():
    """Test 2: 工具分类"""
    print("[Test 2] Tool Categories")
    categories = list_categories()
    print(f"  Categories: {categories}")
    print(f"  By category: {TOOL_STATS['by_category']}")
    assert len(categories) >= 6, "Should have at least 6 categories"
    return True


def test_judgment_tools():
    """Test 3: Judgment 工具"""
    print("[Test 3] Judgment Tools")
    judgment_tools = [name for name, t in TOOL_REGISTRY.items() if t.get("category") == "judgment"]
    print(f"  Count: {len(judgment_tools)}")
    print(f"  Tools: {judgment_tools}")
    assert len(judgment_tools) >= 8, "Should have at least 8 judgment tools"
    return True


def test_memory_tools():
    """Test 4: Memory 工具"""
    print("[Test 4] Memory Tools")
    memory_tools = [name for name, t in TOOL_REGISTRY.items() if t.get("category") == "memory"]
    print(f"  Count: {len(memory_tools)}")
    assert len(memory_tools) >= 8, "Should have at least 8 memory tools"
    return True


def test_get_tool_info():
    """Test 5: 获取工具信息"""
    print("[Test 5] Get Tool Info")
    info = get_tool_info("check10d")
    assert info is not None
    print(f"  check10d: {info}")
    assert info["category"] == "judgment"
    return True


def test_execute_tool_not_found():
    """Test 6: 工具不存在"""
    print("[Test 6] Execute Non-existent Tool")
    from tools import execute_tool
    result = execute_tool("nonexistent_tool_xyz")
    assert not result.success
    assert "not found" in result.error
    print(f"  Error: {result.error}")
    return True


def test_execute_simple_tool():
    """Test 7: 执行简单工具"""
    print("[Test 7] Execute Simple Tool")
    from tools import execute_tool
    from judgment import get_bias_checklist
    
    # 直接调用 bias checklist
    result = execute_tool("get_bias_checklist")
    assert result.success
    print(f"  Success: {result.tool_name}")
    return True


def run_all_tests():
    print("=" * 50)
    print("Juhuo Tools System Tests")
    print("=" * 50)
    
    tests = [
        ("Tool Count", test_tool_count),
        ("Tool Categories", test_tool_categories),
        ("Judgment Tools", test_judgment_tools),
        ("Memory Tools", test_memory_tools),
        ("Get Tool Info", test_get_tool_info),
        ("Non-existent Tool", test_execute_tool_not_found),
        ("Execute Simple Tool", test_execute_simple_tool),
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
            import traceback
            traceback.print_exc()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
