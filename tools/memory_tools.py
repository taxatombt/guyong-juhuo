#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_tools.py — Memory 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class MemoryToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_save_user_memory(content: str, tags: Optional[List[str]] = None) -> MemoryToolResult:
    try:
        from memory_system import save_user_memory
        memory = save_user_memory(content, tags)
        return MemoryToolResult(success=True, result={"id": memory.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_recall_memories(query: str, memory_type: str = "all", limit: int = 5) -> MemoryToolResult:
    try:
        from memory_system import recall_memories
        results = recall_memories(query, memory_type, limit)
        return MemoryToolResult(success=True, result={"count": len(results), "memories": [r.to_dict() for r in results]})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_save_feedback_memory(judgment_id: str, verdict: str, feedback: Optional[str] = None) -> MemoryToolResult:
    try:
        from memory_system import save_feedback_memory
        memory = save_feedback_memory(judgment_id, verdict, feedback)
        return MemoryToolResult(success=True, result={"id": memory.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_save_project_memory(project_id: str, content: str) -> MemoryToolResult:
    try:
        from memory_system import save_project_memory
        memory = save_project_memory(project_id, content)
        return MemoryToolResult(success=True, result={"id": memory.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_save_reference_memory(content: str, reference_type: str, source: str) -> MemoryToolResult:
    try:
        from memory_system import save_reference_memory
        memory = save_reference_memory(content, reference_type, source)
        return MemoryToolResult(success=True, result={"id": memory.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_log_causal_event(event_type: str, description: str, metadata: Optional[Dict] = None) -> MemoryToolResult:
    try:
        from causal_memory import log_causal_event
        event = log_causal_event(event_type, description, metadata)
        return MemoryToolResult(success=True, result={"id": event.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_add_causal_link(cause_id: str, effect_id: str, relation: str) -> MemoryToolResult:
    try:
        from causal_memory import add_causal_link
        link = add_causal_link(cause_id, effect_id, relation)
        return MemoryToolResult(success=True, result={"id": link.id})
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_recall_causal_history(event_id: str, depth: int = 3) -> MemoryToolResult:
    try:
        from causal_memory import recall_causal_history
        history = recall_causal_history(event_id, depth)
        return MemoryToolResult(success=True, result=history)
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


def tool_get_memory_statistics() -> MemoryToolResult:
    try:
        from causal_memory import get_statistics
        stats = get_statistics()
        return MemoryToolResult(success=True, result=stats)
    except Exception as e:
        return MemoryToolResult(success=False, error=str(e))


MEMORY_TOOLS = {
    "save_user_memory": {"fn": tool_save_user_memory, "params": ["content", "tags"]},
    "recall_memories": {"fn": tool_recall_memories, "params": ["query", "memory_type", "limit"]},
    "save_feedback_memory": {"fn": tool_save_feedback_memory, "params": ["judgment_id", "verdict", "feedback"]},
    "save_project_memory": {"fn": tool_save_project_memory, "params": ["project_id", "content"]},
    "save_reference_memory": {"fn": tool_save_reference_memory, "params": ["content", "reference_type", "source"]},
    "log_causal_event": {"fn": tool_log_causal_event, "params": ["event_type", "description", "metadata"]},
    "add_causal_link": {"fn": tool_add_causal_link, "params": ["cause_id", "effect_id", "relation"]},
    "recall_causal_history": {"fn": tool_recall_causal_history, "params": ["event_id", "depth"]},
    "get_memory_statistics": {"fn": tool_get_memory_statistics, "params": []},
}

__all__ = ["MemoryToolResult", "MEMORY_TOOLS"]
