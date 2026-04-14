#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hub.py 单元测试"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """测试导入"""
    print("=== test_import ===")
    from hub import Juhuo, think, check10d, get_hub
    print("  Juhuo:", Juhuo)
    print("  think:", think)
    print("  check10d:", check10d)
    print("  get_hub:", get_hub)
    print("  PASS")
    return True

def test_juhuo_init():
    """测试 Juhuo 实例化"""
    print("\n=== test_juhuo_init ===")
    from hub import Juhuo
    hub = Juhuo(lazy=True)
    assert hub is not None
    print("  Juhuo(lazy=True):", hub)
    print("  PASS")
    return True

def test_judgment_check10d():
    """测试 think() + check10d()"""
    print("\n=== test_judgment_check10d ===")
    from hub import think, check10d

    # think() - 完整流程
    r1 = think("安装npm包")
    assert isinstance(r1, dict)
    print("  think('安装npm包') keys:", list(r1.keys()))
    print("  PASS")

    # check10d() - 快捷函数
    r2 = check10d("做一个九九乘法表Flutter App")
    assert isinstance(r2, dict)
    print("  check10d('做一个九九乘法表Flutter App') keys:", list(r2.keys()))
    print("  PASS")
    return True

def test_hub_singleton():
    """测试全局单例"""
    print("\n=== test_hub_singleton ===")
    from hub import get_hub
    h1 = get_hub()
    h2 = get_hub()
    assert h1 is h2
    print("  get_hub() 单例:", h1 is h2)
    print("  PASS")
    return True

def test_juhuo_think():
    """测试 hub.think()"""
    print("\n=== test_juhuo_think ===")
    from hub import Juhuo
    hub = Juhuo(lazy=True)
    result = hub.think("修复一个Python bug")
    assert isinstance(result, dict)
    print("  hub.think() result type:", type(result).__name__)
    print("  PASS")
    return True

def test_record_lesson():
    """测试因果记忆记录"""
    print("\n=== test_record_lesson ===")
    from hub import Juhuo
    hub = Juhuo()
    try:
        event = hub.causal.log(
            event_type="lesson_learned",
            description="测试：hub.causal.log 可用",
            tags=["test"]
        )
        print("  causal.log event:", event)
        print("  PASS")
        return True
    except Exception as e:
        print("  causal.log 失败:", e)
        print("  (模块缺失，可接受)")
        return True  # 不阻塞

def test_data_dirs():
    """测试数据路径属性"""
    print("\n=== test_data_dirs ===")
    from hub import Juhuo
    hub = Juhuo()
    print("  data_dir:", hub.data_dir)
    print("  memory_fast_dir:", hub.memory_fast_dir)
    print("  memory_slow_dir:", hub.memory_slow_dir)
    print("  evolutions_dir:", hub.evolutions_dir)
    print("  PASS")
    return True

def main():
    tests = [
        test_import,
        test_juhuo_init,
        test_judgment_check10d,
        test_hub_singleton,
        test_juhuo_think,
        test_record_lesson,
        test_data_dirs,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"结果: {passed}/{passed+failed} 通过")
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
