#!/usr/bin/env python3
"""Test gstack virtual team import"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gstack_virtual_team.types import RoleType, Role, Task, ReviewResult, WorkflowState
    print("[OK] gstack_virtual_team.types imported OK")
    
    from gstack_virtual_team.roles import ALL_ROLES, get_role
    print(f"[OK] gstack_virtual_team.roles imported OK, {len(ALL_ROLES)} roles")
    
    from gstack_virtual_team.team import VirtualTeam
    print("[OK] gstack_virtual_team.team imported OK")
    
    from gstack_virtual_team.workflow import GStackWorkflow
    print("[OK] gstack_virtual_team.workflow imported OK")
    
    from gstack_virtual_team.integration import JuhuoGStackIntegration, JuhuoGStackConfig, create_juhuo_virtual_team
    print("[OK] gstack_virtual_team.integration imported OK")
    
    # Test creating team
    team = VirtualTeam()
    enabled = team.get_enabled_roles()
    print(f"\nEnabled roles ({len(enabled)}):")
    for r in enabled:
        print(f"  - {r.name} ({r.role_type.value})")
    
    print("\nALL imports successful! gstack virtual team is ready.")
    
except Exception as e:
    print(f"\n[FAILED] Import failed: {e}")
    import traceback
    traceback.print_exc()
