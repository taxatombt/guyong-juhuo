#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_all_components.py — 全组件验证
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_component(name, module_path, func_name=None):
    """测试单个组件"""
    print(f"\n{'='*50}")
    print(f"测试: {name}")
    print('='*50)
    
    try:
        module = __import__(module_path, fromlist=[''])
        print(f"[OK] 导入成功")
        
        if func_name:
            func = getattr(module, func_name, None)
            if func:
                result = func()
                print(f"[OK] {func_name}() 执行成功")
                return result
            else:
                print(f"[OK] 模块存在 (无{func_name})")
        return True
    except Exception as e:
        import traceback
        print(f"[FAIL] {e}")
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Juhuo 全组件验证")
    print("=" * 60)
    
    results = []
    
    # 1. Judgment系统
    results.append(("Judgment路由", test_component("Judgment路由", "judgment.router")))
    
    # 2. Fitness Evolution
    results.append(("Fitness Evolution", test_component("Fitness Evolution", "judgment.fitness_evolution")))
    
    # 3. Self-Evolver
    results.append(("Self-Evolver", test_component("Self-Evolver", "judgment.self_evolover", "run_evolution_cycle")))
    
    # 4. Causal Memory
    results.append(("Causal Memory", test_component("Causal Memory", "causal_memory")))
    
    # 5. Self-Model
    results.append(("Self-Model", test_component("Self-Model", "self_model.self_model", "load_model")))
    
    # 6. Curiosity
    results.append(("Curiosity", test_component("Curiosity", "curiosity.curiosity_engine", "get_curiosity")))
    
    # 7. Emotion System
    results.append(("Emotion System", test_component("Emotion System", "emotion_system.emotion_system", "detect_emotion")))
    
    # 总结
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\n通过: {passed}/{len(results)}")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
