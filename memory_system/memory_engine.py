#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_engine.py — Juhuo 4类记忆引擎

核心功能：
1. 保存各类记忆
2. 召回相关记忆
3. 判断是否值得保存（铁律：可推导信息不存）

使用方式：
    from memory_system import (
        MemoryEngine,
        save_user_memory, save_feedback_memory,
        save_project_memory, save_reference_memory,
        recall_memories,
    )
    
    # 保存
    save_user_memory("用户是数据科学家，喜欢简洁回答")
    save_feedback_memory("以后遇到这种情况，优先检查配置文件", "guidance")
    
    # 召回
    memories = recall_memories("当前任务描述")
    for m in memories:
        print(f"[{m['type']}] {m['content']}")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
import json
from pathlib import Path

from .memory_types import (
    MemoryType, BaseMemory, UserMemory, FeedbackMemory,
    ProjectMemory, ReferenceMemory,
    generate_id, load_memories, save_memory,
)


# ═══════════════════════════════════════════════════════════════════════════
# 4类记忆保存函数
# ═══════════════════════════════════════════════════════════════════════════

def save_user_memory(
    content: str,
    scope: str = "private",
) -> str:
    """
    保存用户记忆
    
    Args:
        content: 记忆内容（自然语言）
        scope: private | team
        
    Returns:
        memory_id: 记忆ID
    """
    memory_id = generate_id(MemoryType.USER)
    now = datetime.now().isoformat()
    
    memory = {
        "id": memory_id,
        "content": content,
        "scope": scope,
        "created_at": now,
        "updated_at": now,
        "used_count": 0,
        "type": "user",
    }
    
    save_memory(memory, MemoryType.USER)
    return memory_id


def save_feedback_memory(
    content: str,
    outcome: str,
    trigger_context: str = "",
    scope: str = "private",
) -> str:
    """
    保存反馈记忆
    
    Args:
        content: 反馈内容
        outcome: correct | incorrect | guidance
        trigger_context: 触发这个反馈的场景
        scope: private | team
        
    Returns:
        memory_id: 记忆ID
    """
    memory_id = generate_id(MemoryType.FEEDBACK)
    now = datetime.now().isoformat()
    
    memory = {
        "id": memory_id,
        "content": content,
        "scope": scope,
        "created_at": now,
        "updated_at": now,
        "used_count": 0,
        "type": "feedback",
        "trigger_context": trigger_context,
        "outcome": outcome,
    }
    
    save_memory(memory, MemoryType.FEEDBACK)
    return memory_id


def save_project_memory(
    content: str,
    project_id: str,
    status: str = "active",
    scope: str = "private",
) -> str:
    """
    保存项目记忆
    
    Args:
        content: 项目信息内容
        project_id: 关联的项目ID
        status: active | paused | completed | cancelled
        scope: private | team
        
    Returns:
        memory_id: 记忆ID
    """
    memory_id = generate_id(MemoryType.PROJECT)
    now = datetime.now().isoformat()
    
    memory = {
        "id": memory_id,
        "content": content,
        "scope": scope,
        "created_at": now,
        "updated_at": now,
        "used_count": 0,
        "type": "project",
        "project_id": project_id,
        "status": status,
    }
    
    save_memory(memory, MemoryType.PROJECT)
    return memory_id


def save_reference_memory(
    content: str,
    source_system: str,
    source_url: str,
    content_hash: str = "",
    scope: str = "private",
) -> str:
    """
    保存参考记忆
    
    Args:
        content: 参考信息内容
        source_system: 来源系统
        source_url: 来源链接/路径
        content_hash: 内容哈希（用于检测变更）
        scope: private | team
        
    Returns:
        memory_id: 记忆ID
    """
    memory_id = generate_id(MemoryType.REFERENCE)
    now = datetime.now().isoformat()
    
    memory = {
        "id": memory_id,
        "content": content,
        "scope": scope,
        "created_at": now,
        "updated_at": now,
        "used_count": 0,
        "type": "reference",
        "source_system": source_system,
        "source_url": source_url,
        "content_hash": content_hash,
    }
    
    save_memory(memory, MemoryType.REFERENCE)
    return memory_id


# ═══════════════════════════════════════════════════════════════════════════
# 记忆召回
# ═══════════════════════════════════════════════════════════════════════════

def recall_memories(
    query: str,
    memory_types: List[MemoryType] = None,
    limit: int = 5,
) -> List[Dict]:
    """
    根据查询召回相关记忆
    
    Args:
        query: 当前上下文/任务描述
        memory_types: 要召回的类型列表，默认全部
        limit: 最大召回数量
        
    Returns:
        相关记忆列表，按相关性排序
    """
    if memory_types is None:
        memory_types = list(MemoryType)
    
    all_memories = []
    
    for mtype in memory_types:
        memories = load_memories(mtype)
        
        for m in memories:
            # 计算简单相关性分数
            score = _calculate_relevance(query, m)
            if score > 0:
                all_memories.append({
                    **m,
                    "relevance_score": score,
                })
    
    # 按相关性排序
    all_memories.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    # 增加被使用次数
    for m in all_memories[:limit]:
        from .memory_types import increment_used_count
        increment_used_count(m["id"], MemoryType(m["type"]))
    
    return all_memories[:limit]


def _calculate_relevance(query: str, memory: Dict) -> float:
    """
    计算查询与记忆的相关性分数
    
    简单实现：基于关键词匹配
    未来可升级：embedding相似度
    """
    query_lower = query.lower()
    content = memory.get("content", "").lower()
    
    # 提取关键词
    query_words = set(query_lower.split())
    memory_words = set(content.split())
    
    # 计算交集
    intersection = query_words & memory_words
    
    # Jaccard相似度
    union = query_words | memory_words
    if not union:
        return 0.0
    
    # 加权：越常用的词权重越低
    score = 0.0
    for word in intersection:
        # 过滤停用词
        if len(word) < 2:
            continue
        # 完整匹配权重更高
        if word in content:
            score += 0.5
        # 包含匹配
        if word in query_lower and word in content:
            score += 0.3
    
    return min(1.0, score)


# ═══════════════════════════════════════════════════════════════════════════
# 记忆引擎类
# ═══════════════════════════════════════════════════════════════════════════

class MemoryEngine:
    """
    记忆引擎：统一的记忆管理接口
    
    使用方式：
        engine = MemoryEngine()
        
        # 保存
        engine.save("user", "用户是数据科学家")
        engine.save("feedback", "这样做更好", outcome="correct")
        
        # 召回
        relevant = engine.recall("当前任务")
        
        # 检查是否值得保存
        if engine.is_worth_saving("这个信息"):
            engine.save("project", "某个信息")
    """
    
    def __init__(self):
        self._types = list(MemoryType)
    
    def save(
        self,
        memory_type: str,
        content: str,
        **kwargs
    ) -> str:
        """统一保存接口"""
        mtype = MemoryType(memory_type)
        
        if mtype == MemoryType.USER:
            return save_user_memory(content, **kwargs)
        elif mtype == MemoryType.FEEDBACK:
            return save_feedback_memory(content, **kwargs)
        elif mtype == MemoryType.PROJECT:
            return save_project_memory(content, **kwargs)
        elif mtype == MemoryType.REFERENCE:
            return save_reference_memory(content, **kwargs)
        
        raise ValueError(f"Unknown memory type: {memory_type}")
    
    def recall(
        self,
        query: str,
        memory_types: List[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """统一召回接口"""
        if memory_types:
            types = [MemoryType(t) for t in memory_types]
        else:
            types = None
        
        return recall_memories(query, types, limit)
    
    def is_worth_saving(self, info: str) -> bool:
        """
        判断信息是否值得保存（铁律：可推导信息不存）
        
        以下情况不值得保存：
        - 代码模式（可以从代码推导）
        - 架构信息（可以从项目结构推导）
        - Git历史（可以从git log推导）
        - 文件结构（可以从ls/dir推导）
        
        以下情况值得保存：
        - 用户偏好（无法推导）
        - 特定反馈（无法推导）
        - 项目约束（无法推导）
        - 外部系统信息（无法推导）
        """
        info_lower = info.lower()
        
        # 可推导信息关键词（不值得保存）
        derivable_patterns = [
            # 代码/文件相关
            "这个文件", "这段代码", "这个函数", "这个类",
            "在src目录下", "在lib目录下",
            # 架构相关
            "使用了mvc架构", "是微服务", "是单体的",
            # Git相关
            "git commit", "最后一次提交", "最近修改",
            # 通用可推导
            "文件路径是", "代码在", "位于",
        ]
        
        for pattern in derivable_patterns:
            if pattern in info_lower:
                return False
        
        return True
    
    def get_stats(self) -> Dict:
        """获取记忆统计"""
        stats = {}
        for mtype in self._types:
            memories = load_memories(mtype)
            stats[mtype.value] = {
                "count": len(memories),
                "total_used": sum(m.get("used_count", 0) for m in memories),
            }
        return stats


# ═══════════════════════════════════════════════════════════════════════════
# CLI 接口
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Juhuo 4类记忆系统")
    sub = parser.add_subparsers(dest="cmd")
    
    # 保存
    save_p = sub.add_parser("save", help="保存记忆")
    save_p.add_argument("type", choices=["user", "feedback", "project", "reference"])
    save_p.add_argument("content", help="记忆内容")
    save_p.add_argument("--context", default="", help="触发上下文")
    save_p.add_argument("--outcome", default="", help="反馈结果")
    
    # 召回
    recall_p = sub.add_parser("recall", help="召回记忆")
    recall_p.add_argument("query", help="查询内容")
    recall_p.add_argument("--types", nargs="*", choices=["user", "feedback", "project", "reference"])
    recall_p.add_argument("--limit", type=int, default=5)
    
    # 统计
    sub.add_parser("stats", help="记忆统计")
    
    args = parser.parse_args()
    
    engine = MemoryEngine()
    
    if args.cmd == "save":
        kwargs = {}
        if args.context:
            kwargs["trigger_context"] = args.context
        if args.outcome:
            kwargs["outcome"] = args.outcome
        memory_id = engine.save(args.type, args.content, **kwargs)
        print(f"已保存: {memory_id}")
    
    elif args.cmd == "recall":
        memories = engine.recall(args.query, args.types, args.limit)
        if not memories:
            print("无相关记忆")
        else:
            for m in memories:
                print(f"[{m['type']}] {m['content'][:100]}... (score: {m['relevance_score']:.2f})")
    
    elif args.cmd == "stats":
        stats = engine.get_stats()
        for mtype, stat in stats.items():
            print(f"{mtype}: {stat['count']}条记忆, 总使用{stat['total_used']}次")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()