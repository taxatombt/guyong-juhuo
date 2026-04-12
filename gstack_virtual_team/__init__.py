"""
gstack_virtual_team - Garry Tan's gstack virtual engineering team methodology
逆向落地到聚活项目

gstack 核心思想：
- 每个skill是一个专家角色，有明确的职责边界
- 多专家分工协作，每个专家只负责自己专业领域
- 遵循 Boil the Lake 原则：AI 边际成本接近零，做完整的事
- 遵循 Search Before Building 原则：先搜索，再从零开始
- 遵循 User Sovereignty 原则：AI 推荐，用户决策，用户永远在中心

Usage:
    from gstack_virtual_team import create_virtual_team
    team = create_virtual_team("project-name")
"""

from .types import Role, RoleType, Task, ReviewResult, WorkflowState, WorkflowStatus
from .team import VirtualTeam
from .workflow import GStackWorkflow
from .integration import create_juhuo_virtual_team, JuhuoGStackIntegration, JuhuoGStackConfig
from .roles import (
    CEOReviewer,
    ProductManager,
    EngineerReviewer,
    DesignReviewer,
    FrontendDeveloper,
    BackendDeveloper,
    QAReviewer,
    SecurityReviewer,
    DevExReviewer,
    DocsWriter,
    ALL_ROLES,
    get_role,
)

__version__ = "1.0.0"
__all__ = [
    # Types
    "Role",
    "RoleType",
    "Task",
    "ReviewResult",
    "WorkflowState",
    "WorkflowStatus",
    # Core
    "VirtualTeam",
    "GStackWorkflow",
    # Factory / Integration
    "create_juhuo_virtual_team",
    "JuhuoGStackIntegration",
    "JuhuoGStackConfig",
    # Predefined expert roles
    "CEOReviewer",
    "ProductManager",
    "EngineerReviewer",
    "DesignReviewer",
    "FrontendDeveloper",
    "BackendDeveloper",
    "QAReviewer",
    "SecurityReviewer",
    "DevExReviewer",
    "DocsWriter",
    "ALL_ROLES",
    "get_role",
]
