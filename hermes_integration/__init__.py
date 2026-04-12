"""
Hermes-Agent 主动闭环学习集成模块

逆向落地 NousResearch/Hermes-Agent 核心自主进化能力：
- RL from Experience: 从自身执行经验中持续学习改进
- Transparent checkpoint snapshots: 自动文件快照，支持一键回滚
- Persistent curated memory: 持久化结构化记忆，会话启动注入
- Active experience collection: 主动收集执行轨迹，每日自动进化

结合聚活 OpenSpace 三级进化 + 个人数字分身目标：
- 个人一致性作为 reward signal（代替通用任务成功率）
- 身份锁保护核心特质不被 RL 偏离
- 全系统版本快照兼容 OpenSpace DAG 语义
"""

from .utils import get_juhuo_root, get_data_dir
from .active_learning import (
    ActiveLearningLoop,
    ExperienceCollector,
    RewardCalculator,
    Trajectory,
    Experience,
)
from .checkpoint_manager import (
    CheckpointManager,
    create_checkpoint,
    rollback_to_checkpoint,
    list_checkpoints,
)
from .persistent_memory import (
    PersistentMemory,
    MemoryStore,
    add_memory,
    add_user_note,
    replace_memory,
    replace_user_note,
    remove_memory,
    remove_user_note,
    read_memory,
    get_session_snapshot,
)
from .environment_discovery import (
    EnvironmentDiscovery,
    discover_environments,
    EnvironmentInfo,
)

__all__ = [
    # Active Learning
    "ActiveLearningLoop",
    "ExperienceCollector",
    "RewardCalculator",
    "Trajectory",
    "Experience",
    
    # Checkpoint Manager
    "CheckpointManager",
    "create_checkpoint",
    "rollback_to_checkpoint",
    "list_checkpoints",
    
    # Persistent Memory
    "PersistentMemory",
    "MemoryStore",
    "UserMemoryStore",
    "add_memory",
    "replace_memory",
    "remove_memory",
    "read_memory",
    "get_session_snapshot",
    
    # Environment Discovery
    "EnvironmentDiscovery",
    "discover_environments",
    "EnvironmentInfo",
]
