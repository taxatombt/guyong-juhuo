#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evolution_types.py — OpenSpace 类型系统移植到 CoPaw evolver

直接移植自 OpenSpace 核心类型：
- EvolutionType: 三级进化类型 (CAPTURED/DERIVED/FIX)
- SkillMetrics: 质量指标（应用/成功/失败计数）
- SkillLineage: Version DAG 谱系追踪（generation + fix_version + parent）

来源: OpenSpace (HKUDS) — https://github.com/hkuds/OpenSpace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

__all__ = [
    "EvolutionType",
    "SkillMetrics",
    "SkillLineage",
    "SkillVersionDAG",
    "KnowledgeCategory",
]


class KnowledgeCategory(Enum):
    """
    聚活专属：知识分类，决定进化权限（身份锁机制）

    核心身份特质默认锁定，禁止自动进化，仅明确指令可修改。
    """
    CORE_IDENTITY = "CORE_IDENTITY"      # 核心身份特质 — 锁定，禁止自动进化
    SELF_MODEL = "SELF_MODEL"            # 自我认识 — 优先级最高，优先进化
    CAUSAL_MEMORY = "CAUSAL_MEMORY"      # 个人因果记忆 — 优先级高于通用知识
    JUDGMENT_RULE = "JUDGMENT_RULE"      # 判断维度规则 — 允许自动进化
    GENERAL_SKILL = "GENERAL_SKILL"      # 通用技能 — 标准OpenSpace进化
    CURIOSITY = "CURIOSITY"            # 好奇心锁定 — 锁定兴趣域，不乱跑


class EvolutionType(Enum):
    """
    三级进化类型（OpenSpace 核心定义）

    CAPTURED: 捕获全新技能，无父节点 → generation=0
    DERIVED: 从现有技能派生特定场景版本 → generation += 1, fix_version=0
    FIX: 原地修正现有技能 → fix_version += 1, generation 不变
    """
    CAPTURED = "CAPTURED"
    DERIVED = "DERIVED"
    FIX = "FIX"


@dataclass
class SkillMetrics:
    """
    技能质量指标（OpenSpace 全链路质量追踪）

    追踪每次应用结果，计算成功率，驱动进化建议
    """
    applied_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    last_used: Optional[str] = None  # ISO timestamp
    needs_revalidation: bool = False

    @property
    def success_rate(self) -> float:
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count

    def record_application(self, success: bool, timestamp: str):
        """记录一次应用结果"""
        self.applied_count += 1
        self.last_used = timestamp
        if success:
            self.success_count += 1
        else:
            self.failed_count += 1

    def mark_needs_revalidation(self):
        """标记需要重新验证（级联更新）"""
        self.needs_revalidation = True

    def to_dict(self) -> dict:
        return {
            "applied_count": self.applied_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "last_used": self.last_used,
            "needs_revalidation": self.needs_revalidation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillMetrics":
        return cls(
            applied_count=data.get("applied_count", 0),
            success_count=data.get("success_count", 0),
            failed_count=data.get("failed_count", 0),
            last_used=data.get("last_used"),
            needs_revalidation=data.get("needs_revalidation", False),
        )


@dataclass
class SkillLineage:
    """
    SkillLineage — OpenSpace Version DAG 谱系追踪

    两个独立版本维度（OpenSpace 核心设计）:
    - generation: DERIVED 派生深度，每次 DERIVED +1，FIX 不变
    - fix_version: FIX 修正次数，每次 FIX +1，DERIVED 重置为 0

    skill_id 格式: {name}__v{fix_version}_{content_hash}
    """
    skill_name: str
    evolution_type: EvolutionType
    generation: int  # DERIVED depth, 0 for CAPTURED
    fix_version: int  # number of FIXes, 0 for CAPTURED/new DERIVED
    content_hash: str  # sha256 content fingerprint (8 chars)
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    is_active: bool = True  # FIX 会让父节点失活
    metrics: SkillMetrics = field(default_factory=SkillMetrics)

    @property
    def skill_id(self) -> str:
        """Generate skill_id in OpenSpace standard format"""
        return f"{self.skill_name}__v{self.fix_version}_{self.content_hash}"

    def add_child(self, child_id: str):
        """Add a child to lineage"""
        if child_id not in self.child_ids:
            self.child_ids.append(child_id)

    def deactivate(self):
        """Deactivate this node (after FIX / when derived)"""
        self.is_active = False

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "evolution_type": self.evolution_type.value,
            "generation": self.generation,
            "fix_version": self.fix_version,
            "content_hash": self.content_hash,
            "skill_id": self.skill_id,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "is_active": self.is_active,
            "metrics": self.metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillLineage":
        et = EvolutionType(data.get("evolution_type", "CAPTURED"))
        metrics = SkillMetrics.from_dict(data.get("metrics", {}))
        return cls(
            skill_name=data["skill_name"],
            evolution_type=et,
            generation=data["generation"],
            fix_version=data["fix_version"],
            content_hash=data["content_hash"],
            parent_id=data.get("parent_id"),
            child_ids=data.get("child_ids", []),
            is_active=data.get("is_active", True),
            metrics=metrics,
        )


def create_captured(
    skill_name: str,
    content_hash: str,
) -> SkillLineage:
    """Create a new CAPTURED skill (root node)"""
    return SkillLineage(
        skill_name=skill_name,
        evolution_type=EvolutionType.CAPTURED,
        generation=0,
        fix_version=0,
        content_hash=content_hash,
        parent_id=None,
        is_active=True,
    )


def create_derived(
    parent: SkillLineage,
    new_skill_name: str,
    content_hash: str,
) -> SkillLineage:
    """
    Create a DERIVED skill from parent

    - generation = parent.generation + 1
    - fix_version = 0 (new derivation starts at 0)
    - parent remains active
    """
    derived = SkillLineage(
        skill_name=new_skill_name,
        evolution_type=EvolutionType.DERIVED,
        generation=parent.generation + 1,
        fix_version=0,
        content_hash=content_hash,
        parent_id=parent.skill_id,
        is_active=True,
    )
    parent.add_child(derived.skill_id)
    return derived


def create_fix(
    parent: SkillLineage,
    content_hash: str,
) -> SkillLineage:
    """
    Create a FIX for parent

    - generation = same as parent
    - fix_version = parent.fix_version + 1
    - parent becomes inactive (FIX replaces it)
    """
    fixed = SkillLineage(
        skill_name=parent.skill_name,
        evolution_type=EvolutionType.FIX,
        generation=parent.generation,
        fix_version=parent.fix_version + 1,
        content_hash=content_hash,
        parent_id=parent.skill_id,
        is_active=True,
    )
    parent.add_child(fixed.skill_id)
    parent.deactivate()
    return fixed


@dataclass
class SkillVersionDAG:
    """
    SkillVersionDAG — Full version DAG container
    
    Stores all skill lineages, maintains integrity, provides query methods.
    """
    skills: Dict[str, SkillLineage] = field(default_factory=dict)
    db_path: str = "skills-db.json"
    
    def add_skill(self, lineage: SkillLineage) -> None:
        """Add a skill to the DAG"""
        self.skills[lineage.skill_id] = lineage
    
    def get_skill(self, skill_id: str) -> Optional[SkillLineage]:
        """Get skill by id"""
        return self.skills.get(skill_id)
    
    def get_active_skills(self) -> List[SkillLineage]:
        """Get all active skills"""
        return [s for s in self.skills.values() if s.is_active]
    
    def save(self) -> None:
        """Save DAG to disk"""
        data = {
            "skills": {
                skill_id: lineage.to_dict()
                for skill_id, lineage in self.skills.items()
            }
        }
        with open(self.db_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, db_path: str) -> "SkillVersionDAG":
        """Load DAG from disk"""
        import json
        if not Path(db_path).exists():
            return cls(db_path=db_path)
        
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        dag = cls(db_path=db_path)
        for skill_id, skill_dict in data.get("skills", {}).items():
            dag.skills[skill_id] = SkillLineage.from_dict(skill_dict)
        
        return dag
