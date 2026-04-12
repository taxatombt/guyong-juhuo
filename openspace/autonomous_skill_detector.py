#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autonomous_skill_detector.py — Closed-Loop autonomous skill creation/improvement
From Hermes-Agent (NousResearch) insight, integrated to OpenSpace DAG.

Core:
- Detect skill opportunities after task completion
- Score opportunity 0-1
- Suggest creation when ≥ threshold
- Track effectiveness after each use
- Trigger automatic DERIVED improvement when below threshold
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import json
from pathlib import Path

import sys
from pathlib import Path
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution_types import (
    SkillVersionDAG,
    EvolutionType,
    KnowledgeCategory,
)

from openspace_evolution import (
    SkillLineage,
    create_and_save_captured,
    create_and_save_derived,
    create_and_save_fix,
)


@dataclass
class OpportunityScore:
    """Skill opportunity score"""
    score: float  # 0.0 - 1.0
    reasons: List[str]
    should_create: bool


def score_skill_opportunity(
    task_description: str,
    is_repeatable: bool,
    has_consistent_pattern: bool,
    existing_skill_solves: bool,
    done_before: bool,
) -> OpportunityScore:
    """
    Score whether this task should become an autonomous skill.

    Scoring:
    +0.3 — repeatable
    +0.3 — consistent pattern
    +0.2 — not solved by existing skill
    +0.2 — done before (pattern confirmed)
    threshold ≥ 0.5 → suggest create
    """
    score = 0.0
    reasons = []

    if is_repeatable:
        score += 0.3
        reasons.append("Task is repeatable")
    if has_consistent_pattern:
        score += 0.3
        reasons.append("Follows a consistent pattern")
    if not existing_skill_solves:
        score += 0.2
        reasons.append("Not solved well by existing skills")
    if done_before:
        score += 0.2
        reasons.append("Done before — pattern confirmed")

    return OpportunityScore(
        score=round(score, 2),
        reasons=reasons,
        should_create=score >= 0.5,
    )


@dataclass
class UsageStats:
    """Usage effectiveness statistics for a skill"""
    skill_id: str
    total_uses: int = 0
    successful_uses: int = 0
    user_corrections: int = 0
    last_used: Optional[str] = None
    effectiveness: float = 0.0  # 0-1

    def record_use(self, successful: bool, user_corrected: bool) -> None:
        """Record a use of this skill"""
        self.total_uses += 1
        if successful:
            self.successful_uses += 1
        if user_corrected:
            self.user_corrections += 1
        # recalculate effectiveness
        if self.total_uses > 0:
            self.effectiveness = self.successful_uses / self.total_uses

    def should_improve(self, threshold: float = 0.6) -> bool:
        """Should we trigger autonomous improvement?"""
        if self.total_uses < 3:
            return False  # need data
        return self.effectiveness < threshold


class AutonomousSkillTracker:
    """Track autonomous skill effectiveness"""

    def __init__(self, db_path: str = ".skills-db.json"):
        self.db_path = Path(db_path)
        self.stats: Dict[str, UsageStats] = {}
        self._load()

    def _load(self):
        if self.db_path.exists():
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for skill_id, stat in data.items():
                    self.stats[skill_id] = UsageStats(**stat)

    def _save(self):
        data = {
            skill_id: {
                "skill_id": s.skill_id,
                "total_uses": s.total_uses,
                "successful_uses": s.successful_uses,
                "user_corrections": s.user_corrections,
                "last_used": s.last_used,
                "effectiveness": s.effectiveness,
            }
            for skill_id, s in self.stats.items()
        }
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def record_usage(self, skill_id: str, successful: bool, user_corrected: bool) -> UsageStats:
        """Record usage and update stats"""
        if skill_id not in self.stats:
            self.stats[skill_id] = UsageStats(skill_id=skill_id)
        stat = self.stats[skill_id]
        from datetime import datetime
        stat.last_used = datetime.now().isoformat()
        stat.record_use(successful, user_corrected)
        self._save()
        return stat

    def get_stats(self, skill_id: str) -> Optional[UsageStats]:
        return self.stats.get(skill_id)

    def get_skills_needing_improvement(self, threshold: float = 0.6) -> List[str]:
        """Get all skills that need improvement"""
        return [
            skill_id
            for skill_id, stat in self.stats.items()
            if stat.should_improve(threshold)
        ]


def trigger_autonomous_improvement(
    dag: SkillVersionDAG,
    skill_id: str,
    feedback: str,
    tracker: AutonomousSkillTracker,
) -> SkillLineage:
    """
    Trigger autonomous improvement:
    - Derive a new version from current (DERIVED)
    - Incorporate feedback
    - Returns new improved skill
    """
    current = dag.get_skill(skill_id)
    if not current:
        raise ValueError(f"Skill {skill_id} not found")

    # Derive new version (OpenSpace DAG)
    improved = create_and_save_derived(
        dag=dag,
        parent=current,
        new_description=f"{current.description}\n\nAutonomous improvement: {feedback}",
    )

    # Save DAG
    dag.save()

    return improved


def format_opportunity_suggestion(score: OpportunityScore, skill_name: str) -> str:
    """Format suggestion for user"""
    lines = [
        "🔍 Autonomous skill detection found an opportunity!",
        f"Score: {score.score:.2f} | Should create: {'✅ YES' if score.should_create else '❌ NO'}",
        "",
        f"Proposed skill name: **{skill_name}**",
        "Reasons:",
    ]
    for r in score.reasons:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("Should I create this skill? (yes/no)")
    return "\n".join(lines)
