"""
profile_evolution.py — 自我模型进化（盲区追踪+优势强化）

基于历史反馈，自动发现自我盲区，强化优势认知
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import math


@dataclass
class BlindSpot:
    """盲区记录"""
    topic: str  # 盲区话题
    mistakes_count: int  # 错误次数
    confidence: float  # 当前置信度，<0.5 就是盲区
    description: str
    last_occurrence: Optional[str] = None


@dataclass
class Strength:
    """优势记录"""
    topic: str
    correct_count: int
    confidence: float
    description: str


def update_blind_spot(
    current: Dict[str, BlindSpot],
    topic: str,
    mistake: bool,
    description: str = ""
) -> Dict[str, BlindSpot]:
    """
    更新盲区：贝叶斯公式，置信度随错误次数增加

    公式：confidence = min(1.0, 0.2 + 0.16 × mistake_count)
    对数增长，符合认知规律
    """
    if topic in current:
        bs = current[topic]
        if mistake:
            bs.mistakes_count += 1
        bs.description = description or bs.description
        bs.confidence = min(1.0, 0.2 + 0.16 * bs.mistakes_count)
    else:
        count = 1 if mistake else 0
        current[topic] = BlindSpot(
            topic=topic,
            mistakes_count=count,
            confidence=min(1.0, 0.2 + 0.16 * count),
            description=description,
        )

    return current


def update_strength(
    current: Dict[str, Strength],
    topic: str,
    correct: bool,
    description: str = ""
) -> Dict[str, Strength]:
    """
    更新优势：同样贝叶斯更新

    公式：confidence = min(1.0, 0.3 + 0.14 × correct_count)
    """
    if topic in current:
        st = current[topic]
        if correct:
            st.correct_count += 1
        st.description = description or st.description
        st.confidence = min(1.0, 0.3 + 0.14 * st.correct_count)
    else:
        count = 1 if correct else 0
        current[topic] = Strength(
            topic=topic,
            correct_count=count,
            confidence=min(1.0, 0.3 + 0.14 * count),
            description=description,
        )

    return current


def get_blind_spots(blind_spots: Dict[str, BlindSpot], threshold: float = 0.5) -> List[BlindSpot]:
    """获取当前盲区（置信度 < threshold 说明我们知道这里可能错，但需要更多数据）"""
    return [bs for bs in blind_spots.values() if bs.confidence < threshold]


def get_confident_blind_spots(blind_spots: Dict[str, BlindSpot], threshold: float = 0.8) -> List[BlindSpot]:
    """确认的盲区（置信度足够高，这里确实是盲区）"""
    return [bs for bs in blind_spots.values() if bs.confidence >= threshold]


def format_blind_spots(blind_spots: List[BlindSpot]) -> str:
    """格式化盲区列表"""
    if not blind_spots:
        return ""

    lines = ["🔍 【当前发现的盲区】", ""]
    for bs in sorted(blind_spots, key=lambda x: -x.confidence):
        lines.append(f"  • {bs.topic}: 错误次数={bs.mistakes_count} 置信度={bs.confidence:.2f}")
        if bs.description:
            lines.append(f"    {bs.description}")
    lines.append("")

    return "\n".join(lines)


def format_strengths(strengths: List[Strength]) -> str:
    """格式化优势列表"""
    if not strengths:
        return ""

    lines = ["💪 【你的优势领域】", ""]
    for st in sorted(strengths, key=lambda x: -x.confidence):
        lines.append(f"  • {st.topic}: 正确次数={st.correct_count} 置信度={st.confidence:.2f}")
        if st.description:
            lines.append(f"    {st.description}")
    lines.append("")

    return "\n".join(lines)
