#!/usr/bin/env python3
"""Test full system import with gstack"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Import the whole 聚活 system
    import __init__ as juhuo
    print("[OK] juhuo module imported")
    
    from juhuo import gstack_virtual_team
    print("[OK] gstack_virtual_team exported")
    
    from juhuo.gstack_virtual_team import (
        VirtualTeam,
        GStackWorkflow,
        JuhuoGStackIntegration,
        JuhuoGStackConfig,
        create_juhuo_virtual_team,
        Role,
        RoleType,
        Task,
        ReviewResult,
        WorkflowState,
        WorkflowStatus,
    )
    print("[OK] All exports OK")
    
    # Test creating virtual team
    vt = VirtualTeam()
    roles = vt.list_roles()
    print(f"[OK] VirtualTeam created with {len(roles)} total roles")
    
    enabled = vt.get_enabled_roles()
    print(f"[OK] {len(enabled)} roles enabled")
    
    print("\n===== ENABLED ROLES =====")
    for r in enabled:
        print(f"  {r.name} - {r.role_type.value}")
    
    print("\nALL TESTS PASSED. gstack virtual team is fully integrated into 聚活.")
    
except Exception as e:
    print(f"\n[FAILED] {e}")
    import traceback
    traceback.print_exc()
