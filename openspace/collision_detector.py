#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collision_detector.py — Skill 触发条件碰撞检测

集成来源：guyongt skill_collision_detector.py → openspace/
设计原则：
- 检测 skill 触发条件是否重叠/包含/冲突
- 两种碰撞：INCLUDE（包含）/ OVERLAP（部分重叠）
- 碰撞报告供人工确认，避免 skill 互相干扰

碰撞类型：
    INCLUDE：A 的触发条件包含 B（A 会同时触发 B）
    OVERLAP：A 和 B 部分重叠（各自独立但有交集）

使用方式：
    from openspace.collision_detector import SkillCollisionDetector

    detector = SkillCollisionDetector()
    detector.add_skill("tdd", ["test", "TDD", "测试"])
    detector.add_skill("unit-test", ["test", "单元测试", "pytest"])
    collisions = detector.detect_all()
    for c in collisions:
        print(f"[{c.type}] {c.skill_a} <-> {c.skill_b}")
"""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field


@dataclass
class Collision:
    """单条碰撞报告"""
    skill_a: str
    skill_b: str
    type: str  # "INCLUDE" / "OVERLAP"
    detail: str
    shared: List[str] = field(default_factory=list)
    winner: Optional[str] = None


class SkillCollisionDetector:
    """
    Skill 触发条件碰撞检测器

    内部结构：
        skill_name -> set(触发关键词)
    """

    def __init__(self):
        self._skills: Dict[str, Set[str]] = {}

    def add_skill(self, name: str, triggers: List[str]) -> "SkillCollisionDetector":
        """添加一个 skill 及其触发条件"""
        self._skills[name] = set(t.lower().strip() for t in triggers)
        return self

    def add_skill_dict(self, skills: Dict[str, List[str]]) -> "SkillCollisionDetector":
        """批量添加 {name: triggers}"""
        for name, triggers in skills.items():
            self.add_skill(name, triggers)
        return self

    def detect(self, a: str, b: str) -> List[Collision]:
        """检测两个 skill 之间是否有碰撞"""
        if a not in self._skills or b not in self._skills:
            return []
        set_a = self._skills[a]
        set_b = self._skills[b]
        shared = set_a & set_b
        if not shared:
            return []

        collisions = []
        if set_a >= set_b:
            collisions.append(Collision(
                skill_a=a, skill_b=b, type="INCLUDE",
                detail=f"'{a}' 的触发条件完全包含 '{b}'",
                shared=list(shared), winner=a,
            ))
        elif set_b >= set_a:
            collisions.append(Collision(
                skill_a=a, skill_b=b, type="INCLUDE",
                detail=f"'{b}' 的触发条件完全包含 '{a}'",
                shared=list(shared), winner=b,
            ))
        else:
            collisions.append(Collision(
                skill_a=a, skill_b=b, type="OVERLAP",
                detail=f"'{a}' 和 '{b}' 有 {len(shared)} 个共同触发词",
                shared=list(shared),
            ))
        return collisions

    def detect_all(self) -> List[Collision]:
        """检测所有 skill 两两之间的碰撞"""
        names = list(self._skills.keys())
        results = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                results.extend(self.detect(a, b))
        return results

    def detect_for(self, skill_name: str) -> List[Collision]:
        """检测指定 skill 与所有其他 skill 的碰撞"""
        results = []
        for other in self._skills:
            if other != skill_name:
                results.extend(self.detect(skill_name, other))
        return results

    def resolve_include(self, collision: Collision) -> str:
        """解决 INCLUDE 碰撞：保留触发词更多的"""
        len_a = len(self._skills.get(collision.skill_a, set()))
        len_b = len(self._skills.get(collision.skill_b, set()))
        if len_a > len_a:
            return collision.skill_a
        elif len_b > len_a:
            return collision.skill_b
        return min(collision.skill_a, collision.skill_b)

    def report(self, collisions: List[Collision]) -> str:
        """生成人类可读的碰撞报告"""
        if not collisions:
            return "SAFE: No skill collisions detected"
        lines = [f"WARNING: Detected {len(collisions)} skill collision(s):\n"]
        for c in collisions:
            lines.append(f"[{c.type}] {c.skill_a} <-> {c.skill_b}")
            lines.append(f"  Shared: {', '.join(c.shared)}")
            lines.append(f"  Detail: {c.detail}")
            if c.winner:
                lines.append(f"  Suggested: keep '{c.winner}'")
            lines.append("")
        return "\n".join(lines)
