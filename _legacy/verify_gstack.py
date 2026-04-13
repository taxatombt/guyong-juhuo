#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from gstack_virtual_team import VirtualTeam, GStackWorkflow, Role, RoleType, create_juhuo_virtual_team, ALL_ROLES
print('[OK] gstack 所有模块导入成功')
print(f'[OK] 预定义专家角色: {len(ALL_ROLES)} 个')
print()
for r in ALL_ROLES:
    print(f'  - {r.name}: {r.description[:60]}...')
print()
print('✓ gstack 模块验证通过！')
