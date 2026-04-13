#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from hermes_evolution import HermesEvolution, SkillStorage, TrajectoryRecorder
print('[OK] HermesEvolution 导入成功')

evolution = HermesEvolution()
stats = evolution.get_stats()
print(f'[OK] Hermes 统计: {stats}')
print()
print('✓ Hermes 模块验证通过！')
