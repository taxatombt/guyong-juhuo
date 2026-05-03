#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
query_engine.py — MAGMA 风格查询引擎

功能：
1. 查询意图分类（semantic / temporal / causal / entity）
2. 生成拓扑检索路径
3. 决定启用哪些图谱及权重

灵感来源：豆包 MAGMA 记忆系统
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional
import re


class QueryType(Enum):
    """查询类型枚举"""
    SEMANTIC = "semantic"       # 语义相似：关于什么、是什么
    TEMPORAL = "temporal"       # 时间相关：什么时候、过去如何、近期
    CAUSAL = "causal"           # 因果关系：为什么、因为什么、导致
    ENTITY = "entity"           # 实体相关：谁、哪个项目、什么工具
    MIXED = "mixed"             # 混合类型


@dataclass
class QueryIntent:
    """查询意图"""
    raw_query: str
    query_type: QueryType
    # 各图谱权重（0-1，越高越优先）
    weights: Dict[str, float] = field(default_factory=dict)
    # 拓扑路径节点（用于因果检索）
    traversal_path: List[str] = field(default_factory=list)
    # 置信度
    confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 查询意图分类器
# ═══════════════════════════════════════════════════════════════════════════

# 时间相关关键词
_TEMPORAL_KEYWORDS = [
    r"什么时候", r"何时", r"过去", r"以前", r"最近",
    r"昨天", r"上周", r"这周", r"这个月", r"去年",
    r"近期", r"一直以来", r"曾经", r"之前", r"今后",
    r"历史", r"上一次的", r"上一次", r"从头到尾",
]

# 因果相关关键词
_CAUSAL_KEYWORDS = [
    r"为什么", r"因为", r"导致", r"所以", r"因此",
    r"原因", r"结果", r"由于", r"致使", r"造成",
    r"根源", r"起因", r"后果", r"为了", r"目的",
    r"为什么会", r"怎么会", r"是什么导致",
]

# 实体相关关键词
_ENTITY_KEYWORDS = [
    r"谁", r"哪个人", r"哪个项目", r"哪个工具",
    r"哪个文件", r"哪个模块", r"哪个函数",
    r"叫什么", r"是什么工具", r"是谁",
]

# 语义相关关键词（偏概念理解）
_SEMANTIC_KEYWORDS = [
    r"是什么", r"关于", r"如何", r"怎样",
    r"什么意思", r"概念", r"定义", r"区别",
]


def classify(query: str) -> QueryIntent:
    """
    分类查询意图，决定启用哪些图谱及权重

    Args:
        query: 自然语言查询

    Returns:
        QueryIntent：包含类型、权重、拓扑路径
    """
    q = query.strip()
    q_lower = q.lower()

    # 统计各类型命中
    scores = {
        "semantic": _count_matches(q, _SEMANTIC_KEYWORDS),
        "temporal": _count_matches(q, _TEMPORAL_KEYWORDS),
        "causal": _count_matches(q, _CAUSAL_KEYWORDS),
        "entity": _count_matches(q, _ENTITY_KEYWORDS),
    }

    # 特殊模式检测
    if re.search(r"(过去|以前|曾经|历史).*经验", q):
        scores["temporal"] += 2
        scores["causal"] += 1
    if re.search(r"(为什么|原因|因为).*(导致|造成)", q):
        scores["causal"] += 3
    if re.search(r"谁.*做的|谁.*说|人名|名字", q):
        scores["entity"] += 2

    # 判断主导类型
    max_score = max(scores.values())

    if max_score == 0:
        # 默认走语义检索
        dominant = QueryType.SEMANTIC
        weights = {"semantic": 0.7, "temporal": 0.1, "causal": 0.1, "entity": 0.1}
        confidence = 0.5
    elif list(scores.values()).count(max_score) > 1:
        # 多类型平分 → 混合
        dominant = QueryType.MIXED
        weights = {k: 0.25 for k in scores}
        confidence = 0.6
    else:
        dominant = QueryType(
            list(scores.keys())[list(scores.values()).index(max_score)]
        )
        # 权重分配：主导类型占主导权重
        w = {k: 0.0 for k in scores}
        w[dominant.value] = 0.7
        # 剩余权重按比例分配
        remaining = 0.3
        total_other = sum(v for k, v in scores.items() if k != dominant.value)
        if total_other > 0:
            for k in w:
                if k != dominant.value:
                    w[k] = remaining * (scores[k] / total_other)
        weights = w
        confidence = min(0.5 + max_score * 0.15, 0.95)

    # 生成拓扑路径（用于因果检索）
    path = _build_traversal_path(q, dominant)

    return QueryIntent(
        raw_query=q,
        query_type=dominant,
        weights=weights,
        traversal_path=path,
        confidence=confidence,
    )


def _count_matches(text: str, patterns: List[str]) -> int:
    """统计文本中匹配的模式数量"""
    count = 0
    for p in patterns:
        if re.search(p, text):
            count += 1
    return count


def _build_traversal_path(query: str, qtype: QueryType) -> List[str]:
    """根据查询类型生成拓扑遍历路径"""
    # 提取关键概念词（去停用词后）
    stop_words = {"的", "是", "在", "了", "和", "与", "或", "我", "你", "他", "她", "它"}
    words = [w for w in re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", query)
             if w not in stop_words and len(w) > 1]

    if qtype == QueryType.CAUSAL:
        # 因果检索：从结果词 → 原因词逆拓扑遍历
        cause_words = [w for w in words if w in _CAUSAL_KEYWORDS]
        # 加入原始词作为中间节点
        return words[:3]  # 最多3个节点
    elif qtype == QueryType.TEMPORAL:
        # 时间检索：从现在 → 过去逆序
        return list(reversed(words[:3]))
    elif qtype == QueryType.ENTITY:
        # 实体检索：精确节点查询
        return words[:2]
    else:
        # 语义检索：语义扩展
        return words[:3]


def get_top_k_types(intent: QueryIntent, top_k: int = 2) -> List[Tuple[str, float]]:
    """获取权重最高的 top_k 个图谱"""
    sorted_weights = sorted(
        intent.weights.items(), key=lambda x: x[1], reverse=True
    )
    return sorted_weights[:top_k]


# ═══════════════════════════════════════════════════════════════════════════
# 检索结果融合（加权分数合并）
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RetrievalResult:
    """单条检索结果"""
    memory_id: str
    content: str
    graph_type: str          # 来自哪个图谱
    raw_score: float         # 该图谱原始分数
    weighted_score: float     # 加权后分数
    metadata: Dict = field(default_factory=dict)


def fuse_results(
    results_by_graph: Dict[str, List[RetrievalResult]],
    intent: QueryIntent,
) -> List[RetrievalResult]:
    """
    多图谱检索结果融合

    策略：
    1. 按 weighted_score 合并所有结果
    2. 同一 memory_id 取最高分（避免重复）
    3. 按加权分数降序
    """
    # Step 1: 合并所有图谱结果
    all_results: List[RetrievalResult] = []
    for graph_type, results in results_by_graph.items():
        all_results.extend(results)

    # Step 2: 同一 memory_id 取最高加权分数
    best_by_id: Dict[str, RetrievalResult] = {}
    for r in all_results:
        if r.memory_id not in best_by_id or \
           r.weighted_score > best_by_id[r.memory_id].weighted_score:
            best_by_id[r.memory_id] = r

    # Step 3: 排序输出
    fused = sorted(
        best_by_id.values(),
        key=lambda x: x.weighted_score,
        reverse=True,
    )
    return fused