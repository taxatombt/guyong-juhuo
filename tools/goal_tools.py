#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
goal_tools.py — Goal 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class GoalToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_set_goal(text: str, deadline: Optional[str] = None, priority: int = 5) -> GoalToolResult:
    """设置目标"""
    try:
        from goal_system import GoalSystem
        system = GoalSystem()
        goal = system.set_goal(text, deadline, priority)
        return GoalToolResult(success=True, result={"id": goal.id, "text": goal.text})
    except Exception as e:
        return GoalToolResult(success=False, error=str(e))


def tool_get_goals(status: str = "active") -> GoalToolResult:
    """获取目标列表"""
    try:
        from goal_system import GoalSystem
        system = GoalSystem()
        goals = system.get_goals(status)
        return GoalToolResult(success=True, result={"count": len(goals), "goals": [g.to_dict() for g in goals]})
    except Exception as e:
        return GoalToolResult(success=False, error=str(e))


def tool_update_goal_progress(goal_id: str, progress: float) -> GoalToolResult:
    """更新目标进度"""
    try:
        from goal_system import GoalSystem
        system = GoalSystem()
        system.update_progress(goal_id, progress)
        return GoalToolResult(success=True, result={"updated": True})
    except Exception as e:
        return GoalToolResult(success=False, error=str(e))


def tool_complete_goal(goal_id: str) -> GoalToolResult:
    """完成目标"""
    try:
        from goal_system import GoalSystem
        system = GoalSystem()
        system.complete(goal_id)
        return GoalToolResult(success=True, result={"completed": True})
    except Exception as e:
        return GoalToolResult(success=False, error=str(e))


GOAL_TOOLS = {
    "set_goal": {"fn": tool_set_goal, "params": ["text", "deadline", "priority"]},
    "get_goals": {"fn": tool_get_goals, "params": ["status"]},
    "update_goal_progress": {"fn": tool_update_goal_progress, "params": ["goal_id", "progress"]},
    "complete_goal": {"fn": tool_complete_goal, "params": ["goal_id"]},
}

__all__ = ["GoalToolResult", "GOAL_TOOLS"]
