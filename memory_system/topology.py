#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topology.py — 因果链拓扑遍历层

灵感来源：豆包 MAGMA 因果图谱 + Codex Matcher 拓扑路径

功能：
1. 从 correlation_memory 加载因果链，构建拓扑图
2. 按拓扑顺序遍历，找出因果路径
3. 对检索查询计算拓扑相关度分数
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path
import json
import re

# ─────────────────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CausalNode:
    """拓扑节点：对应一个因果事件"""
    event_id: int
    description: str
    timestamp: str
    outcome: str = ""       # good / bad / neutral
    tags: List[str] = field(default_factory=list)


@dataclass
class CausalEdge:
    """拓扑边：因果关系"""
    from_id: int
    to_id: int
    relation: str           # causes / enables / prevents / contradicts
    weight: float = 1.0    # 因果强度


@dataclass
class TopoPath:
    """拓扑检索路径"""
    nodes: List[CausalNode]
    edges: List[CausalEdge]
    path_score: float
    explanation: str


# ─────────────────────────────────────────────────────────────────────────────
# 拓扑遍历器
# ─────────────────────────────────────────────────────────────────────────────

class CausalTopology:
    """
    因果链拓扑遍历器

    构建 DAG（有向无环图）并提供：
    - forward_traverse: 从因到果
    - backward_traverse: 从果到因
    - find_path: 找两节点间的最短因果路径
    - score_by_topology: 给定查询词，计算拓扑相关度
    """

    def __init__(self):
        self.nodes: Dict[int, CausalNode] = {}
        self.edges_out: Dict[int, List[CausalEdge]] = {}  # from_id -> edges
        self.edges_in: Dict[int, List[CausalEdge]] = {}   # to_id -> edges
        self._load_from_correlation_memory()

    def _load_from_correlation_memory(self):
        """从 correlation_memory 加载因果链，构建拓扑图"""
        try:
            import sqlite3
            from pathlib import Path as P
            db_path = P(__file__).parent.parent / "data" / "correlation_memory" / "events.db"
            if not db_path.exists():
                return
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # 加载事件节点
            cur.execute(
                "SELECT event_id, description, timestamp, outcome FROM causal_events ORDER BY event_id"
            )
            for row in cur.fetchall():
                event_id, description, timestamp, outcome = row
                node = CausalNode(
                    event_id=event_id,
                    description=description or "",
                    timestamp=timestamp or "",
                    outcome=outcome or "neutral",
                    tags=self._extract_tags(description),
                )
                self.nodes[event_id] = node
                self.edges_out[event_id] = []
                self.edges_in[event_id] = []

            # 加载因果链接边
            cur.execute(
                "SELECT from_event_id, to_event_id, relation, weight FROM causal_links"
            )
            for row in cur.fetchall():
                from_id, to_id, relation, weight = row
                if from_id in self.nodes and to_id in self.nodes:
                    edge = CausalEdge(
                        from_id=from_id,
                        to_id=to_id,
                        relation=relation or "causes",
                        weight=weight if weight is not None else 1.0,
                    )
                    self.edges_out[from_id].append(edge)
                    self.edges_in[to_id].append(edge)

            conn.close()
        except Exception:
            # correlation_memory 可能还没初始化，优雅降级
            pass

    def _extract_tags(self, text: str) -> List[str]:
        """从事件描述中提取标签"""
        stop = {"的", "是", "在", "了", "和", "与", "或", "我", "你",
                "他", "这个", "那个", "一个", "一些", "什么", "怎么"}
        words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", text.lower())
        return [w for w in words if w not in stop and len(w) >= 2][:5]

    # ───────────────────────────────────────────────────────────────────
    # 遍历方法
    # ───────────────────────────────────────────────────────────────────

    def forward_traverse(
        self,
        start_id: int,
        max_depth: int = 3,
    ) -> List[TopoPath]:
        """
        前向遍历：从因到果

        Returns:
            从起点出发的所有可达路径
        """
        paths = []
        self._dfs_forward(start_id, [start_id], [], paths, max_depth)
        return paths

    def backward_traverse(
        self,
        end_id: int,
        max_depth: int = 3,
    ) -> List[TopoPath]:
        """
        后向遍历：从果到因（追溯根因）

        Returns:
            到达终点的所有溯源路径
        """
        paths = []
        self._dfs_backward(end_id, [end_id], [], paths, max_depth)
        return paths

    def _dfs_forward(
        self,
        current: int,
        path_ids: List[int],
        path_edges: List[CausalEdge],
        results: List[TopoPath],
        max_depth: int,
    ):
        if len(path_ids) > max_depth + 1:
            return
        if current not in self.edges_out or not self.edges_out[current]:
            # 叶子节点，输出路径
            if len(path_ids) > 1:
                nodes = [self.nodes[i] for i in path_ids]
                score = self._path_score(nodes, path_edges)
                results.append(TopoPath(
                    nodes=nodes,
                    edges=path_edges.copy(),
                    path_score=score,
                    explanation=f"前向路径：{' → '.join(str(i) for i in path_ids)}",
                ))
            return
        for edge in self.edges_out[current]:
            self._dfs_forward(
                edge.to_id,
                path_ids + [edge.to_id],
                path_edges + [edge],
                results,
                max_depth,
            )

    def _dfs_backward(
        self,
        current: int,
        path_ids: List[int],
        path_edges: List[CausalEdge],
        results: List[TopoPath],
        max_depth: int,
    ):
        if len(path_ids) > max_depth + 1:
            return
        if current not in self.edges_in or not self.edges_in[current]:
            if len(path_ids) > 1:
                nodes = [self.nodes[i] for i in path_ids]
                edges_rev = [CausalEdge(
                    from_id=e.to_id, to_id=e.from_id,
                    relation=e.relation, weight=e.weight
                ) for e in reversed(path_edges)]
                score = self._path_score(nodes, edges_rev)
                results.append(TopoPath(
                    nodes=nodes,
                    edges=edges_rev,
                    path_score=score,
                    explanation=f"后向路径：{' → '.join(str(i) for i in reversed(path_ids))}",
                ))
            return
        for edge in self.edges_in[current]:
            self._dfs_backward(
                edge.from_id,
                path_ids + [edge.from_id],
                path_edges + [edge],
                results,
                max_depth,
            )

    def _path_score(self, nodes: List[CausalNode], edges: List[CausalEdge]) -> float:
        """计算路径综合分数"""
        if not nodes:
            return 0.0
        # 节点覆盖率
        coverage = len(nodes) / max(len(nodes), 1)
        # 边权重均值
        avg_weight = sum(e.weight for e in edges) / max(len(edges), 1) if edges else 0.0
        return coverage * 0.5 + avg_weight * 0.5

    # ───────────────────────────────────────────────────────────────────
    # 查询评分
    # ───────────────────────────────────────────────────────────────────

    def score_by_query(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Tuple[int, float, str]]:
        """
        给定查询词，对所有节点计算拓扑相关度

        Args:
            query: 查询词
            top_k: 返回前k个

        Returns:
            List[(event_id, score, reason)]
        """
        query_words = set(re.findall(
            r"[\u4e00-\u9fa5a-zA-Z0-9]{2,}", query.lower()
        ))
        scores = []

        for event_id, node in self.nodes.items():
            # 节点标签匹配
            node_words = set(node.tags)
            overlap = len(query_words & node_words)
            # 因果关系词匹配
            causal_bonus = 0.0
            causal_markers = {"因为", "导致", "所以", "原因", "结果", "为了"}
            for marker in causal_markers:
                if marker in (node.description or "").lower():
                    causal_bonus += 0.1

            # 度中心性加成（出/入边越多越重要）
            centrality = (
                len(self.edges_out.get(event_id, [])) +
                len(self.edges_in.get(event_id, []))
            ) * 0.05

            score = overlap * 0.5 + causal_bonus + centrality
            scores.append((event_id, score,
                           f"标签重叠{overlap} + 因果{causal_bonus:.2f} + 中心性{centrality:.2f}"))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    # ───────────────────────────────────────────────────────────────────
    # 批量索引（供外部调用）
    # ───────────────────────────────────────────────────────────────────

    def build_from_memories(self, memories: List[Dict]):
        """
        从记忆列表构建拓扑索引

        供 memory_engine 在召回时使用
        """
        for m in memories:
            self.index_memory_from_dict(m)

    def index_memory_from_dict(self, memory: Dict):
        """将一条记忆字典转为拓扑节点"""
        from .four_graph import _extract_entities, _time_bucket
        event_id = hash(memory.get("id", "")) % 1000000
        node = CausalNode(
            event_id=event_id,
            description=memory.get("content", ""),
            timestamp=memory.get("created_at", ""),
            outcome=memory.get("outcome", ""),
            tags=_extract_entities(memory.get("content", "")),
        )
        self.nodes[event_id] = node


# ═════════════════════════════════════════════════════════════════════════════════
# 单例
# ═════════════════════════════════════════════════════════════════════════════════

_causal_topology: Optional[CausalTopology] = None


def get_causal_topology() -> CausalTopology:
    """获取因果拓扑单例"""
    global _causal_topology
    if _causal_topology is None:
        _causal_topology = CausalTopology()
    return _causal_topology