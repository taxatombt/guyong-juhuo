"""
recursive_trigger.py — 递归深度探测

对于低置信度维度，自动触发递归追问，挖深认知
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class RecursiveProbe:
    """递归探测结果"""
    depth_reached: int
    total_probes: int
    probes: List[Dict]  # [{"dimension": ..., "question": ..., "score": ...}]


# 探测启发问题
PROBE_QUESTIONS = {
    "low": [
        "你对这个判断的置信度为什么低？",
        "缺少什么关键信息？",
        "有没有可能我的前提错了？",
    ],
    "medium": [
        "这个判断足够谨慎吗？",
        "是否过度思考了？",
        "这个结论还有其他解释吗？",
    ],
    "high": [
        "这个结论真的站得住脚吗？",
        "如果站在对立面，会怎么反驳？",
    ]
}


def recursive_probe(
    confidence_scores: Dict[str, float],
    threshold: float = 0.5,
    max_depth: int = 2,
    max_probes: int = 5
) -> RecursiveProbe:
    """
    触发递归探测

    参数:
        confidence_scores: 维度置信度 {dim_id: score}
        threshold: 低于这个分数触发探测
        max_depth: 最大探测深度
        max_probes: 最大问题数
    """
    low_dims = [(dim, score) for dim, score in confidence_scores.items() if score < threshold]
    # 按置信度升序，最低的优先探测
    low_dims.sort(key=lambda x: x[1])

    probes = []
    depth = 0
    for dim, score in low_dims[:max_probes]:
        # 根据置信度选问题
        if score < 0.3:
            questions = PROBE_QUESTIONS["low"]
        elif score < 0.5:
            questions = PROBE_QUESTIONS["medium"]
        else:
            questions = PROBE_QUESTIONS["high"]

        for q in questions[:1]:  # 每个维度只问一个，避免太多
            probes.append({
                "dimension": dim,
                "question": q,
                "score": score,
            })
            depth += 1
            if depth >= max_probes:
                break
        if depth >= max_probes:
            break

    return RecursiveProbe(
        depth_reached=min(depth, max_depth),
        total_probes=len(probes),
        probes=probes
    )


def format_recursive_probe(result: RecursiveProbe) -> str:
    """格式化递归探测"""
    if result.total_probes == 0:
        return ""

    lines = ["🔍 【递归深度探测】", ""]
    for p in result.probes:
        dim = p["dimension"]
        lines.append(f"  [{dim}({p['score']:.2f})] ❓ {p['question']}")
    lines.append("")

    return "\n".join(lines)
