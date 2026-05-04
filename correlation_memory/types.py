#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
types.py — 因果记忆数据类型定义

借鉴 OpenSpace 进化模式分类：
- FIX: 修正现有因果链接
- DERIVED: 从现有链接衍生特定场景版本
- CAPTURED: 捕获全新因果链接
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict


class EvolutionType(Enum):
    """因果链接进化类型，借鉴 OpenSpace"""
    FIX = "FIX"           # 修正现有链接（置信度/关系错误）
    DERIVED = "DERIVED"   # 从父链接衍生特定场景版本
    CAPTURED = "CAPTURED" # 捕获全新因果链接


class CausalRelation(Enum):
    """因果关系类型"""
    SIMILAR_TASK = "similar_task"     # 相似任务
    PRECEDES = "precedes"             # 时间上先于
    CAUSES = "causes"                 # 直接导致
    INFLUENCES = "influences"         # 影响
    DEPENDS_ON = "depends_on"         # 依赖于


@dataclass
class CausalEvent:
    """因果事件节点（单次判断/决策）"""
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
class CausalLinkQuality:
    """因果链接质量追踪（借鉴 OpenSpace 全栈质量监控）"""
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
class CausalLink:
    """因果链接（两个事件之间的因果关系）"""
    link_id: int
    from_event_id: int
    to_event_id: int
    relation: str  # CausalRelation
    confidence: float
    timestamp: str
    inferred: bool = False  # False=快路径, True=慢路径推断
    evolution_type: Optional[str] = None  # EvolutionType
    parent_link_id: Optional[int] = None  # DERIVED 时的父链接
    quality: CausalLinkQuality = field(default_factory=CausalLinkQuality)

    def to_dict(self) -> Dict:
        """转换为字典用于JSON序列化"""
        return {
            "link_id": self.link_id,
            "from_event_id": self.from_event_id,
            "to_event_id": self.to_event_id,
            "relation": self.relation,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "inferred": self.inferred,
            "evolution_type": self.evolution_type,
            "parent_link_id": self.parent_link_id,
            "quality": {
                "applied_count": self.quality.applied_count,
                "success_count": self.quality.success_count,
                "failed_count": self.quality.failed_count,
                "last_checked": self.quality.last_checked,
                "needs_revalidation": self.quality.needs_revalidation,
                "dependent_link_ids": self.quality.dependent_link_ids,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CausalLink":
        """从字典恢复"""
        quality_data = data.get("quality", {})
        quality = CausalLinkQuality(
            applied_count=quality_data.get("applied_count", 0),
            success_count=quality_data.get("success_count", 0),
            failed_count=quality_data.get("failed_count", 0),
            last_checked=quality_data.get("last_checked"),
            needs_revalidation=quality_data.get("needs_revalidation", False),
            dependent_link_ids=quality_data.get("dependent_link_ids", []),
        )
        return cls(
            link_id=data["link_id"],
            from_event_id=data["from_event_id"],
            to_event_id=data["to_event_id"],
            relation=data["relation"],
            confidence=data["confidence"],
            timestamp=data["timestamp"],
            inferred=data.get("inferred", False),
            evolution_type=data.get("evolution_type"),
            parent_link_id=data.get("parent_link_id"),
            quality=quality,
        )


@dataclass
class EvolutionSuggestion:
    """进化建议，借鉴 OpenSpace"""
    link_id: int
    evolution_type: EvolutionType
    reason: str
    current_confidence: float
    suggested_confidence: Optional[float] = None
    new_relation: Optional[str] = None
    depends_on_changed: bool = False  # 依赖的链接已改变，需要重新验证


@dataclass
class CausalStats:
    """因果记忆统计"""
    total_events: int
    total_links: int
    inferred_links: int
    fast_path_links: int
    by_evolution_type: Dict[str, int]
    avg_success_rate: float
    links_needing_revalidation: int
