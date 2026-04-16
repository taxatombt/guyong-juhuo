#!/usr/bin/env python3
"""最终验证脚本"""
import sys
sys.path.insert(0, ".")

from judgment.self_evolover import run_evolution_cycle, sync_to_self_model, get_cases, compute_new_weights

print("=" * 60)
print("Self-Evolver 最终验证")
print("=" * 60)

# 1. 检查数据
cases = get_cases()
print(f"\n[1] 历史案例: {len(cases)} 条")

if cases:
    weights = compute_new_weights(cases)
    print(f"[2] 可用权重: {weights}")

# 2. 运行闭环
print("\n[3] 运行Self-Evolver闭环...")
result = run_evolution_cycle()
print(f"状态: {result['status']}")

if result.get('triggered'):
    print(f"✅ 触发原因: {result['trigger']['reason']}")
    print(f"✅ 优胜者: {result['winner']}")
    print(f"✅ 提升: {result.get('improvement', 0):.2%}")
else:
    print(f"[i] 未触发: {result['trigger']['reason']}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
