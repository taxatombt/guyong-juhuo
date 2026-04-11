"""
embedding_match.py — 嵌入相似度匹配

找到历史上相似决策，提供参考经验
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class SimilarMatch:
    """相似匹配结果"""
    decision_id: str
    text: str
    similarity: float
    outcome: Optional[str] = None
    lesson: Optional[str] = None


# 简化版本：基于关键词匹配（真正嵌入版本需要额外依赖）
# 可以扩展到 Sentence-BERT 等，保持接口兼容

DIM_KEYWORDS = {
    "cognitive": ["认知", "思考", "分析", "直觉", "假设", "事实", "偏差", "系统"],
    "game_theory": ["博弈", "对方", "竞争", "合作", "策略", "利益", "均衡"],
    "economic": ["成本", "收益", "机会", "经济", "边际", "不可逆"],
    "dialectics": ["矛盾", "辩证", "对立", "转化", "主次", "主要矛盾"],
    "emotional": ["情绪", "感受", "焦虑", "兴奋", "恐惧", "心态"],
    "intuitive": ["直觉", "第六感", "感觉", "第一反应", "经验"],
    "moral": ["道德", "对错", "原则", "价值观", "责任", "良心"],
    "social": ["他人", "社会", "群体", "身份", "认同", "看法", "评价"],
    "temporal": ["时间", "长期", "短期", "五年", "复利", "折扣"],
    "metacognitive": ["思考", "反思", "元认知", "盲区", "自我"],
}


def keyword_overlap(a: str, b: str) -> float:
    """简单关键词重叠计算相似度"""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    return len(intersection) / max(len(a_words), len(b_words))


def find_similar_decisions(
    query: str,
    history: List[Dict],
    top_k: int = 5
) -> List[SimilarMatch]:
    """
    在历史决策中找相似

    参数:
        query: 当前查询文本
        history: 历史列表 [{id, text, outcome, lesson}, ...]
        top_k: 返回top k
    """
    scored = []
    for item in history:
        sim = keyword_overlap(query, item.get("text", ""))
        scored.append((sim, SimilarMatch(
            decision_id=item.get("id", ""),
            text=item.get("text", ""),
            similarity=sim,
            outcome=item.get("outcome"),
            lesson=item.get("lesson"),
        )))

    # 按相似度降序
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:top_k]]


def format_similar_matches(matches: List[SimilarMatch]) -> str:
    """格式化相似匹配结果"""
    if not matches:
        return "无历史相似决策"

    lines = ["【历史相似决策】", ""]
    for i, m in enumerate(matches):
        lines.append(f"{i+1}. [{m.similarity:.0%}] {m.text[:60]}")
        if m.lesson:
            lines.append(f"   💡 教训: {m.lesson}")
        if m.outcome:
            lines.append(f"   📊 结果: {m.outcome}")
        lines.append("")

    return "\n".join(lines)
