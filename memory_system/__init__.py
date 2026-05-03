#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_system — Juhuo 4类记忆系统

导入入口
"""

from .memory_types import (
    MemoryType,
    BaseMemory,
    UserMemory,
    FeedbackMemory,
    ProjectMemory,
    ReferenceMemory,
    generate_id,
    load_memories,
    save_memory,
    increment_used_count,
)

from .memory_engine import (
    MemoryEngine,
    save_user_memory,
    save_feedback_memory,
    save_project_memory,
    save_reference_memory,
    recall_memories,
)

# MAGMA 四路检索
from .query_engine import (
    QueryIntent,
    QueryType,
    RetrievalResult,
    classify,
    get_top_k_types,
    fuse_results,
)

from .four_graph import FourGraphIndex, SearchResult

from .topology import CausalTopology, TopoPath

__all__ = [
    # 原有
    "MemoryType",
    "BaseMemory",
    "UserMemory",
    "FeedbackMemory",
    "ProjectMemory",
    "ReferenceMemory",
    "generate_id",
    "load_memories",
    "save_memory",
    "increment_used_count",
    "MemoryEngine",
    "save_user_memory",
    "save_feedback_memory",
    "save_project_memory",
    "save_reference_memory",
    "recall_memories",
    # MAGMA 四路检索
    "QueryIntent",
    "QueryType",
    "RetrievalResult",
    "classify",
    "get_top_k_types",
    "fuse_results",
    "FourGraphIndex",
    "SearchResult",
    "CausalTopology",
    "TopoPath",
]
