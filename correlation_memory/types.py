#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
types.py — 关联记忆数据类型定义

借鉴 OpenSpace 进化模式分类：
- FIX: 修正现有关联链接
- DERIVED: 从现有链接衍生特定场景版本
- CAPTURED: 捕获全新关联链接
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict


class EvolutionType(Enum):
    """关联链接进化类型，借鉴 OpenSpace"""
    FIX = "FIX"           # 修正现有链接（置信度/关系错误）
    DERIVED = "DERIVED"   # 从父链接衍生特定场景版本
    CAPTURED = "CAPTURED" # 捕获全新关联链接


class CorrelationRelation(Enum):
    """关联关系类型"""
    SIMILAR_TASK = "similar_task"     # 相似任务
    PRECEDES = "precedes"             # 时间上先于
    CAUSES = "causes"                 # 直接导致
    INFLUENCES = "influences"         # 影响
    DEPENDS_ON = "depends_on"         # 依赖于


@dataclass
class CorrelationEvent:
    """关联事件节点（单次判断/决策）"""
    event_id: int
    timestamp: str
    task: str
    complexity: Optional[str] = None
    dimensions_checked: int = 0
    must_check: List[str] = field(default_factory=list)
    important: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    agent_profile: Optional[str] = None
    decision: str = ""
    feedback: Optional[str] = None
    outcome: Optional[bool] = None  # True=成功/正确, False=失败/错误


@dataclass
class CorrelationLinkQuality:
    """关联链接质量追踪（借鉴 OpenSpace 全栈质量监控）"""
    applied_count: int = 0       # 总应用次数
    success_count: int = 0       # 成功次数
    failed_count: int = 0        # 失败次数
    last_checked: Optional[str] = None  # 最后检查时间
    needs_revalidation: bool = False   # 是否需要重新验证（级联更新标记）
    dependent_link_ids: List[int] = field(default_factory=list)  # 依赖此链接的上游链接

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count

    def record_application(self, success: bool):
        """记录一次应用结果"""
        self.applied_count += 1
        if success:
            self.success_count += 1
        else:
            self.failed_count += 1
        self.last_checked = datetime.now().isoformat()

    def mark_needs_revalidation(self):
        """标记需要重新验证（级联更新，借鉴 OpenSpace 级联进化）"""
        self.needs_revalidation = True


@dataclass
class CorrelationLink:
    """关联链接（两个事件之间的关联关系）"""
    link_id: int
    from_event_id: int
    to_event_id: int
    relation: str  # CorrelationRelation
    confidence: float
    timestamp: str
    inferred: bool = False  # False=快路径, True=慢路径推断
    source_event_ids: List[int] = field(default_factory=list)
    quality: Optional[CorrelationLinkQuality] = None
    domain: Optional[str] = None
    context: Optional[str] = None
    avg_score: Optional[float] = None
    cooccurrence_count: Optional[int] = None


@dataclass
class EvolutionSuggestion:
    """关联链接进化建议（来自 OpenSpace 启发）"""
    link_id: int
    evolution_type: EvolutionType
    reason: str
    parent_link_id: Optional[int] = None
    new_confidence: Optional[float] = None
    new_relation: Optional[str] = None


@dataclass
class CorrelationStats:
    """关联记忆统计"""
    total_events: int = 0
    total_links: int = 0
    inferred_links: int = 0
    domains: Dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    high_quality_links: int = 0  # 成功率 >= 0.7 的链接数
