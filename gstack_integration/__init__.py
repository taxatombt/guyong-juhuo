"""
gstack_integration - Garry Tan's gstack virtual engineering team integration
Incorporates the 23-specialist workflow into Juhuo (聚活) self-evolution system

Core idea: Turn Juhuo into a personal virtual team for your digital Doppelgänger
- Role-based specialization (CEO/Product/Arch/Design/QA/Security/Release)
- Complete workflow: Think → Plan → Build → Review → Test → Ship → Reflect
- Persistent browser daemon for automated QA (borrows from gstack architecture)
"""

from gstack_integration.gstack_workflow import (
    GStackWorkflow,
    GStackWorkflowState,
    RoleTask,
    WorkflowStage,
    create_gstack_workflow,
)
from gstack_integration.role_prompts import (
    RoleType,
    RoleDefinition,
    get_role_prompt,
    ROLES,
)

__all__ = [
    "GStackWorkflow",
    "RoleType",
    "WorkflowStage",
    "create_gstack_workflow",
    "get_role_prompt",
    "ROLES",
]
