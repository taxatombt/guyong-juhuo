"""
profile.py — 个人认知档案

存储个人身份、认知风格、目标系统，用于对齐决策一致性
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json
from pathlib import Path


@dataclass
class PersonalProfile:
    """个人认知档案"""
    name: str  # 档案名称
    description: str  # 档案描述

    # 核心身份特质（锁定，不自动进化）
    core_identity: Dict[str, str]
    # 锁定的兴趣领域（好奇心只在这个域游走）
    locked_interests: List[str]

    # 认知风格
    cognitive_style: Dict[str, float]  # {维度: 权重 0-1}
    # 价值观权重
    value_weights: Dict[str, float]

    # 五年/年度/月度目标
    five_year_goals: List[str]
    annual_goals: List[str]
    monthly_milestones: List[str]

    # 默认配置
    confidence_threshold: float = 0.5
    curiosity_probability: float = 0.2

    def to_dict(self):
        return asdict(self)

    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)


# 默认空模板
DEFAULT_PROFILE = PersonalProfile(
    name="default",
    description="默认个人认知档案",
    core_identity={
        "style": "理性优先，实事求是",
        "orientation": "长期主义，价值投资",
    },
    locked_interests=[
        "AI Agent", "认知科学", "方法论", "哲学", "心理学"
    ],
    cognitive_style={
        "cognitive": 1.0,
        "game_theory": 0.8,
        "economic": 0.9,
        "dialectics": 1.0,
        "emotional": 0.5,
        "intuitive": 0.5,
        "moral": 0.8,
        "social": 0.6,
        "temporal": 0.9,
        "metacognitive": 1.0,
    },
    value_weights={
        "long_term": 0.8,
        "integrity": 1.0,
        "growth": 0.9,
        "contribution": 0.7,
    },
    five_year_goals=[
        "完成聚活系统，真正实现自我克隆"
    ],
    annual_goals=[
        "完善所有核心模块",
        "沉淀足够多认知数据"
    ],
    monthly_milestones=[
        "迭代一次核心功能"
    ]
)


def load_profile(path: str = "profiles/default.json") -> PersonalProfile:
    """加载档案，如果不存在创建默认"""
    p = Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_PROFILE.save(path)
        return DEFAULT_PROFILE
    return PersonalProfile.load(path)


def check_goals_alignment(
    decision_text: str,
    profile: PersonalProfile,
    goals_db: List[Dict] = None
) -> Dict:
    """
    检查决策和目标体系的对齐程度

    返回各层级对齐得分和整体结论
    """
    if goals_db is None:
        goals_db = [
            {"goal": g, "timeframe": "five_year"} for g in profile.five_year_goals
        ] + [
            {"goal": g, "timeframe": "annual"} for g in profile.annual_goals
        ] + [
            {"goal": g, "timeframe": "monthly"} for g in profile.monthly_milestones
        ]

    # 关键词匹配打分
    timeframe_weight = {
        "five_year": 0.5,
        "annual": 0.3,
        "monthly": 0.2,
    }

    total_score = 0.0
    total_weight = 0.0
    aligned = []
    misaligned = []

    for goal in goals_db:
        text = goal["goal"]
        tf = goal.get("timeframe", "monthly")
        w = timeframe_weight.get(tf, 0.2)

        # 简单关键词重叠算对齐
        decision_words = set(decision_text.lower().split())
        goal_words = set(text.lower().split())
        overlap = len(decision_words & goal_words) / max(len(goal_words), 1)

        score = overlap
        total_score += score * w
        total_weight += w

        if score > 0.2:
            aligned.append({"goal": text, "timeframe": tf, "score": score})
        else:
            misaligned.append({"goal": text, "timeframe": tf, "score": score})

    overall_alignment = total_score / total_weight if total_weight else 0.5

    return {
        "overall_alignment": overall_alignment,
        "aligned_goals": aligned,
        "misaligned_goals": misaligned,
        "has_archetype": overall_alignment < 0.3,
        "verdict": (
            "STRONG_ALIGN" if overall_alignment > 0.7 else
            "PARTIAL_ALIGN" if overall_alignment > 0.3 else
            "POOR_ALIGN"
        )
    }
