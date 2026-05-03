#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
four_graph.py — 四图谱检索引擎

灵感来源：豆包 MAGMA 记忆系统
- 语义图谱：embedding 相似度
- 时间图谱：时间线遍历 + 周期性分组
- 因果图谱：causal_memory 链拓扑
- 实体图谱：命名实体共现网络

设计原则：
- 每条记忆入库时同时写入四图谱索引
- 检索时按 query_engine 的权重动态选择图谱
- 与现有 JSONL 存储兼容（索引只是加速层）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
import json
import math
import re
from pathlib import Path

from .memory_types import MemoryType


INDEX_DIR = Path(__file__).parent / "memories" / "_graph_index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class GraphNode:
    """图谱节点"""
    memory_id: str
    content: str
    created_at: str
    memory_type: str
    # 语义向量（简化：用内容hash作为伪向量ID）
    vec_id: str = ""
    # 时间标签
    time_bucket: str = ""   # "2026-05" / "2026-W18" / "recent"
    # 实体列表
    entities: List[str] = field(default_factory=list)
    # 因果标签
    causal_tags: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """检索结果"""
    memory_id: str
    content: str
    score: float
    graph_type: str
    reason: str  # 得分原因说明


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════

def _time_bucket(iso_str: str) -> str:
    """将 ISO 时间字符串转为时间桶标签"""
    try:
        dt = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return "unknown"

    now = datetime.now()
    delta = (now - dt).days

    if delta <= 7:
        return "recent"
    elif delta <= 30:
        return "this_month"
    elif delta <= 90:
        return "recent_quarter"
    else:
        return f"y{dt.year}-m{dt.month:02d}"


def _extract_entities(content: str) -> List[str]:
    """简单实体提取（关键词 + 专有名词）"""
    # 停用词
    stop = {"的", "是", "在", "了", "和", "与", "或", "我", "你", "他",
            "她", "它", "这个", "那个", "什么", "如何", "怎么", "怎样",
            "一个", "一些", "可以", "应该", "可能", "会", "能", "要"}
    words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9_]{2,}", content.lower())
    # 过滤停用词和过短词
    entities = [w for w in words if w not in stop and len(w) >= 2]
    # 简单去重保留频率前5
    freq = {}
    for e in entities:
        freq[e] = freq.get(e, 0) + 1
    return sorted(freq.keys(), key=lambda x: freq[x], reverse=True)[:5]


def _extract_causal_tags(content: str) -> List[str]:
    """从内容中提取因果标签"""
    causal_markers = [
        "因为", "导致", "所以", "因此", "由于",
        "结果是", "原因是", "造成", "致使",
        "为了", "目的", "导致", "因果",
    ]
    tags = []
    content_lower = content.lower()
    for marker in causal_markers:
        if marker in content_lower:
            tags.append(marker)
    return tags


def _simple_hash(s: str) -> str:
    """简化哈希（用于伪向量ID）"""
    import hashlib
    return hashlib.md5(s.encode()).hexdigest()[:16]


def _cosine_sim_hash(vec_a: str, vec_b: str) -> float:
    """简化 cosine 相似度：基于字符集重合率"""
    if not vec_a or not vec_b:
        return 0.0
    set_a = set(vec_a)
    set_b = set(vec_b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 四图谱检索
# ═══════════════════════════════════════════════════════════════════════════

class FourGraphIndex:
    """
    四图谱索引管理器

    索引存储格式：JSON Lines
    每个 memory_id 一行，包含四图谱所需的全部元数据
    """

    INDEX_FILE = INDEX_DIR / "four_graph.jsonl"

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._load()

    def _load(self):
        """从磁盘加载索引"""
        if not self.INDEX_FILE.exists():
            return
        try:
            with open(self.INDEX_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    node_dict = json.loads(line)
                    node = GraphNode(**node_dict)
                    self._nodes[node.memory_id] = node
        except (json.JSONDecodeError, Exception):
            pass

    def _save(self):
        """持久化索引到磁盘"""
        with open(self.INDEX_FILE, "w", encoding="utf-8") as f:
            for node in self._nodes.values():
                f.write(json.dumps(node.__dict__, ensure_ascii=False) + "\n")

    def index_memory(
        self,
        memory_id: str,
        content: str,
        created_at: str,
        memory_type: str,
    ):
        """将一条记忆加入四图谱索引"""
        node = GraphNode(
            memory_id=memory_id,
            content=content,
            created_at=created_at,
            memory_type=memory_type,
            vec_id=_simple_hash(content),
            time_bucket=_time_bucket(created_at),
            entities=_extract_entities(content),
            causal_tags=_extract_causal_tags(content),
        )
        self._nodes[memory_id] = node
        self._save()

    def remove_memory(self, memory_id: str):
        """从索引中移除一条记忆"""
        if memory_id in self._nodes:
            del self._nodes[memory_id]
            self._save()

    # ───────────────────────────────────────────────────────────────────
    # 语义图谱检索
    # ───────────────────────────────────────────────────────────────────
    def semantic_search(
        self, query: str, memories: List[Dict], top_k: int = 5
    ) -> List[SearchResult]:
        """
        语义图谱检索：基于 embedding 相似度

        当前实现：伪向量（内容hash相似度）
        未来可升级：调用真实 embedding API
        """
        query_hash = _simple_hash(query)
        results = []

        for m in memories:
            m_hash = _simple_hash(m.get("content", ""))
            # 简化 cosine 相似度
            sim = _cosine_sim_hash(query_hash, m_hash)
            # 同时考虑关键词重合
            keywords = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", query.lower()))
            content_words = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}",
                                          m.get("content", "").lower()))
            keyword_overlap = len(keywords & content_words) / max(len(keywords), 1)
            # 综合分数
            score = sim * 0.4 + keyword_overlap * 0.6
            if score > 0.05:  # 阈值过滤
                results.append(SearchResult(
                    memory_id=m["id"],
                    content=m["content"],
                    score=score,
                    graph_type="semantic",
                    reason=f"语义相似度 {score:.2f}（hash {sim:.2f} + 关键词 {keyword_overlap:.2f}）",
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    # ───────────────────────────────────────────────────────────────────
    # 时间图谱检索
    # ───────────────────────────────────────────────────────────────────
    def temporal_search(
        self, query: str, memories: List[Dict], top_k: int = 3
    ) -> List[SearchResult]:
        """
        时间图谱检索：按时间近邻 + 查询时间意图

        时间意图判断：
        - "过去" / "以前" / "曾经" → 越老越相关
        - "最近" / "现在" / "这次" → 越新越相关
        - 无时间词 → 默认新优先
        """
        q_lower = query.lower()
        reverse = bool(re.search(r"过去|以前|曾经", q_lower))

        results = []
        for m in memories:
            created = m.get("created_at", "")
            bucket = _time_bucket(created)
            bucket_scores = {
                "recent": 1.0, "this_month": 0.8,
                "recent_quarter": 0.6, "unknown": 0.2,
            }
            base_score = bucket_scores.get(bucket, 0.3)

            keywords = set(re.findall(
                r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", q_lower
            ))
            content_words = set(re.findall(
                r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}",
                m.get("content", "").lower()
            ))
            keyword_overlap = len(keywords & content_words) / max(len(keywords), 1)
            score = base_score * 0.6 + keyword_overlap * 0.4

            if score > 0.1:
                results.append(SearchResult(
                    memory_id=m["id"],
                    content=m["content"],
                    score=score,
                    graph_type="temporal",
                    reason=f"时间桶 {bucket} × 关键词 {keyword_overlap:.2f}",
                ))

        results.sort(key=lambda x: x.score, reverse=not reverse)
        return results[:top_k]

    # ───────────────────────────────────────────────────────────────────
    # 因果图谱检索
    # ───────────────────────────────────────────────────────────────────
    def causal_search(
        self,
        query: str,
        memories: List[Dict],
        traversal_path: List[str],
        top_k: int = 3,
    ) -> List[SearchResult]:
        """
        因果图谱检索：基于因果标签 + 拓扑路径匹配
        """
        causal_markers = {
            "因为", "导致", "所以", "因此", "由于",
            "结果是", "原因是", "造成", "致使",
        }
        query_words = set(re.findall(
            r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", query.lower()
        ))

        results = []
        for m in memories:
            content_lower = m.get("content", "").lower()
            content_words = set(re.findall(
                r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", content_lower
            ))
            marker_count = sum(1 for marker in causal_markers
                               if marker in content_lower)
            marker_score = min(marker_count * 0.25, 1.0)
            path_match = sum(1 for node in traversal_path
                             if node in content_lower)
            path_score = path_match / max(len(traversal_path), 1)
            keyword_overlap = len(query_words & content_words) / max(len(query_words), 1)
            score = marker_score * 0.4 + path_score * 0.3 + keyword_overlap * 0.3

            if score > 0.05:
                results.append(SearchResult(
                    memory_id=m["id"],
                    content=m["content"],
                    score=score,
                    graph_type="causal",
                    reason=f"因果 {marker_score:.2f} + 路径 {path_score:.2f} + 关键词 {keyword_overlap:.2f}",
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    # ───────────────────────────────────────────────────────────────────
    # 实体图谱检索
    # ───────────────────────────────────────────────────────────────────
    def entity_search(
        self, query: str, memories: List[Dict], top_k: int = 3
    ) -> List[SearchResult]:
        """
        实体图谱检索：基于命名实体共现
        """
        query_entities = _extract_entities(query)
        if not query_entities:
            return []

        results = []
        for m in memories:
            content_entities = _extract_entities(m.get("content", ""))
            overlap = len(set(query_entities) & set(content_entities))
            score = overlap / max(len(query_entities), 1)

            if score > 0.1:
                results.append(SearchResult(
                    memory_id=m["id"],
                    content=m["content"],
                    score=score,
                    graph_type="entity",
                    reason=f"实体 {overlap}/{len(query_entities)}: "
                            f"{set(query_entities) & set(content_entities)}",
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
_four_graph_index = None

def get_four_graph_index():
    """Get four-graph index singleton"""
    global _four_graph_index
    if _four_graph_index is None:
        _four_graph_index = FourGraphIndex()
    return _four_graph_index
