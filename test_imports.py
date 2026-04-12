#!/usr/bin/env python3
"""Test all imports for Hermes and gstack modules."""

import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    from hermes_evolution import HermesEvolution, SkillStorage, TrajectoryRecorder
    print('[OK] Hermes evolution imported successfully')
    
    evolution = HermesEvolution()
    stats = evolution.get_stats()
    print(f'[OK] Stats retrieved: {stats}')
    print('\n[OK] All Hermes modules imported successfully')
except Exception as e:
    print(f'[ERROR] Hermes import failed: {e}')
    import traceback
    traceback.print_exc()

try:
    from gstack_virtual_team import (
        VirtualTeam, 
        GStackWorkflow, 
        Role, 
        RoleType, 
        create_juhuo_virtual_team,
        JuhuoGStackIntegration,
        JuhuoGStackConfig,
        ALL_ROLES,
    )
    print('[OK] gstack virtual team imported successfully')
    print(f'[OK] Loaded {len(ALL_ROLES)} predefined expert roles')
except Exception as e:
    print(f'[ERROR] gstack import failed: {e}')
    import traceback
    traceback.print_exc()

print('\n=== All imports test completed ===')
