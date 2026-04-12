#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gstack_virtual_team.types import RoleType, WorkflowState
print('OK - types imported')

from gstack_virtual_team.roles import ALL_ROLES
print('OK - roles imported, {0} roles'.format(len(ALL_ROLES)))

from gstack_virtual_team.team import VirtualTeam
print('OK - team imported')

from gstack_virtual_team.workflow import GStackWorkflow
print('OK - workflow imported')

from gstack_virtual_team.integration import JuhuoGStackIntegration, JuhuoGStackConfig, create_juhuo_virtual_team
print('OK - integration imported')

# Test creating a team
vt = VirtualTeam()
enabled = vt.get_enabled_roles()
print('VirtualTeam created, {0} enabled roles'.format(len(enabled)))

print('\n===== SUCCESS =====')
print('All gstack_virtual_team modules imported successfully!')
