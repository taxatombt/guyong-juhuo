#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_skills.py - Skill系统测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills import registry


def test_list_skills():
    """Test 1: List all skills"""
    skills = registry.list_all()
    print(f"[Test 1] Found {len(skills)} skills")
    for s in skills[:5]:
        print(f"  - {s.name}: {s.description[:40]}...")
    assert len(skills) > 0, "Should have skills"
    return True


def test_help_skill():
    """Test 2: Help skill"""
    result = registry.execute("help")
    assert result.error is None, f"Help failed: {result.error}"
    assert "skills" in result.result
    print(f"[Test 2] Help skill works, returned {len(result.result.get('skills', []))} skills")
    return True


def test_emotion_skill():
    """Test 3: Emotion skill"""
    result = registry.execute("emotion", "I am anxious about this decision")
    assert result.error is None, f"Emotion failed: {result.error}"
    print(f"[Test 3] Emotion skill works")
    return True


def test_code_review_skill():
    """Test 4: Code review skill"""
    result = registry.execute("code_review", 'password = "secret123"')
    assert result.error is None, f"Code review failed: {result.error}"
    assert result.result.get("has_issues") == True
    assert "硬编码密码" in result.result.get("issues", [])
    print(f"[Test 4] Code review found: {result.result.get('issues')}")
    return True


def test_find_by_trigger():
    """Test 5: Find skills by trigger"""
    # 测试能匹配上的词
    skills = registry.find_by_trigger("code review")
    print(f"[Test 5] Found {len(skills)} skills for 'code review': {[s.name for s in skills]}")
    assert len(skills) > 0, "Should find code_review skill"
    return True


def test_search_skill():
    """Test 6: Search skill"""
    result = registry.execute("search", "Python best practices")
    assert result.error is None
    print(f"[Test 6] Search skill works")
    return True


def test_unknown_skill():
    """Test 7: Unknown skill error"""
    result = registry.execute("unknown_skill_xyz")
    assert result.error is not None
    assert "not found" in result.error
    print(f"[Test 7] Unknown skill correctly returns error: {result.error}")
    return True


def run_all_tests():
    print("=" * 50)
    print("Juhuo Skill System Tests")
    print("=" * 50)
    
    tests = [
        ("List skills", test_list_skills),
        ("Help skill", test_help_skill),
        ("Emotion skill", test_emotion_skill),
        ("Code review skill", test_code_review_skill),
        ("Find by trigger", test_find_by_trigger),
        ("Search skill", test_search_skill),
        ("Unknown skill error", test_unknown_skill),
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
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
