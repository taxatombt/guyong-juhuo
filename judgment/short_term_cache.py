# -*- coding: utf-8 -*-
"""
ShortTermCache — L1 会话缓存（ZeusHammer 三层记忆启发）

位置：judgment/short_term_cache.py
数据：内存（进程内），不落盘

设计目标：
  - 减少重复的 LLM 调用
  - 会话内跨任务共享上下文
  - 与 L2（experiences SQLite）和 L3（FTS5语义）配合

三层记忆架构：
  L1 短时：ShortTermCache（内存 OrderedDict，TTL=3600s）← 本文件
  L2 长时：experiences SQLite（跨会话，embedding 检索）
  L3 向量：FTS5 bm25（语义搜索）

核心用法：
    from judgment.short_term_cache import short_term_cache

    # 存判断上下文（当前会话内）
    short_term_cache.set(f"ctx:{chain_id}", {
        "task": "要不要all in炒股？",
        "verdict": "谨慎决策",
        "confidence": 0.85,
        "emotion_pad": {"P": -0.3, "A": 0.4, "D": -0.2}
    })

    # 查相关上下文（同一会话内）
    ctx = short_term_cache.get_similar("all in炒股")
    if ctx:
        return ctx  # 复用缓存，减少 LLM 调用

    # 全量获取（对话开头用）
    all_contexts = short_term_cache.get_all()
"""

import time
import hashlib
import re
from collections import OrderedDict
from typing import Optional, Dict, Any, List


class ShortTermCache:
    """
    L1 短时缓存：会话内上下文缓存

    特性：
    - OrderedDict 实现，LRU 驱逐
    - TTL 过期（默认 3600 秒）
    - importance 加权（重要缓存不易被驱逐）
    - 相似任务检索（关键词 bigram）
    """

    def __init__(self, max_size: int = 50, default_ttl: int = 3600):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl

    # ── 基础操作 ────────────────────────────────────────────────────────

    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None,
            importance: int = 1) -> None:
        """
        存缓存

        Args:
            key: 缓存键
            value: 缓存值（dict，应包含 task/verdict/confidence 等字段）
            ttl: 过期秒数（默认 self._default_ttl）
            importance: 重要性 1-5，重要性高的缓存不易被 LRU 驱逐
        """
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + ttl

        entry = {
            "value": value,
            "expires_at": expires_at,
            "importance": max(1, min(5, importance)),  # 限制在 1-5
            "created_at": time.time(),
            "hit_count": 0,
        }

        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            # LRU 驱逐：先驱逐不重要且最旧的
            while len(self._cache) >= self._max_size:
                self._evict_one()

        self._cache[key] = entry

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """取缓存（同时提升 hit_count 和 LRU 位置）"""
        if key not in self._cache:
            return None

        entry = self._cache[key]

        # TTL 过期检查
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            return None

        # LRU 提升 + hit 计数
        self._cache.move_to_end(key)
        entry["hit_count"] += 1

        return entry["value"]

    def delete(self, key: str) -> bool:
        """删除指定缓存"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()

    # ── LRU 驱逐 ────────────────────────────────────────────────────────

    def _evict_one(self) -> bool:
        """
        驱逐一条缓存（LUR + 低 importance 优先）
        Returns: True if evicted, False if nothing to evict
        """
        if not self._cache:
            return False

        # 找 importance 最低且最老的
        worst_key = None
        worst_score = float("inf")

        for key, entry in self._cache.items():
            # score = importance * recency（importance 低 + 老的先驱逐）
            age = time.time() - entry["created_at"]
            score = entry["importance"] * (age / 3600.0)  # age 按小时归一化
            if score < worst_score:
                worst_score = score
                worst_key = key

        if worst_key:
            del self._cache[worst_key]
            return True
        return False

    # ── 相似任务检索 ────────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(text: str) -> set:
        """
        从文本提取关键词 bigram（用于相似度匹配）
        """
        # 中文 bigram
        chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        chinese_bigrams = {text[i:i+2] for i in range(len(chinese_chars) - 1)}

        # 英文词
        english_words = set(re.findall(r'[a-zA-Z]{2,}', text.lower()))

        # 数字+单位词
        number_words = set(re.findall(r'[\u4e00-\u9fff0-9]+', text))

        return chinese_bigrams | english_words | number_words

    def get_similar(self, query: str, top_k: int = 3,
                    min_overlap: float = 0.3) -> List[Dict[str, Any]]:
        """
        查找与 query 相似的缓存条目

        Args:
            query: 查询文本
            top_k: 返回最多 top_k 条
            min_overlap: 最小重叠率（0.0~1.0）

        Returns:
            按相似度降序排列的缓存条目列表
        """
        query_kw = self._extract_keywords(query)
        if not query_kw:
            return []

        results = []
        now = time.time()

        for key, entry in self._cache.items():
            # TTL 过期跳过
            if now > entry["expires_at"]:
                continue

            value = entry["value"]
            task_text = value.get("task", "")

            entry_kw = self._extract_keywords(task_text)
            if not entry_kw:
                continue

            # Jaccard 相似度
            overlap = len(query_kw & entry_kw)
            union = len(query_kw | entry_kw)
            jaccard = overlap / union if union > 0 else 0.0

            if jaccard >= min_overlap:
                results.append({
                    "key": key,
                    "jaccard": jaccard,
                    "hit_count": entry["hit_count"],
                    "importance": entry["importance"],
                    "created_at": entry["created_at"],
                    "value": value,
                })

        # 按 jaccard 降序，hit_count 次之
        results.sort(key=lambda x: (x["jaccard"], x["hit_count"]), reverse=True)
        return results[:top_k]

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有未过期的缓存（用于对话开头构建上下文）"""
        now = time.time()
        all_entries = []
        for key, entry in self._cache.items():
            if now <= entry["expires_at"]:
                all_entries.append({
                    "key": key,
                    "created_at": entry["created_at"],
                    "importance": entry["importance"],
                    "hit_count": entry["hit_count"],
                    "value": entry["value"],
                })
        return all_entries

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = time.time()
        expired = sum(1 for e in self._cache.values() if now > e["expires_at"])
        return {
            "total": len(self._cache),
            "max": self._max_size,
            "expired": expired,
            "active": len(self._cache) - expired,
            "total_hits": sum(e["hit_count"] for e in self._cache.values()),
        }

    def prune_expired(self) -> int:
        """删除所有过期条目，返回删除数量"""
        now = time.time()
        expired_keys = [k for k, e in self._cache.items() if now > e["expires_at"]]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)


# ── 全局单例 ────────────────────────────────────────────────────────────

short_term_cache = ShortTermCache(max_size=50, default_ttl=3600)


# ── 集成到 router ─────────────────────────────────────────────────────

def inject_short_term_context(task_text: str, top_k: int = 3) -> str:
    """
    从 L1 缓存获取与 task_text 相似的上下文，生成提示文本

    在 check10d 之前调用，如果缓存命中则可减少 LLM 调用。
    """
    results = short_term_cache.get_similar(task_text, top_k=top_k)
    if not results:
        return ""

    lines = ["[会话历史参考]"]
    for r in results:
        v = r["value"]
        verdict = v.get("verdict", "（无判断结论）")
        conf = v.get("confidence", 0)
        lines.append(f"  - 任务：{v.get('task', '')}")
        lines.append(f"    结论：{verdict}（置信度 {conf:.0%}）")
    lines.append("[参考完毕]\n")

    return "\n".join(lines)

