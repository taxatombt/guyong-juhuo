#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
action_tools.py — Action 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ActionToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_plan_action(task: str, context: Optional[Dict] = None) -> ActionToolResult:
    """行动规划"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        plan = system.plan(task, context or {})
        return ActionToolResult(success=True, result=plan.to_dict())
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


def tool_execute_action(action_id: str) -> ActionToolResult:
    """执行行动"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        result = system.execute(action_id)
        return ActionToolResult(success=True, result={"executed": result})
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


def tool_log_action(action: str, outcome: str) -> ActionToolResult:
    """记录行动"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        system.log_action(action, outcome)
        return ActionToolResult(success=True, result={"logged": True})
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


def tool_get_next_action(priority: str = "high") -> ActionToolResult:
    """获取下一步行动"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        action = system.get_next(priority)
        return ActionToolResult(success=True, result=action.to_dict() if action else None)
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


def tool_check_security(action: str) -> ActionToolResult:
    """安全检查"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        safe, reason = system.check_security(action)
        return ActionToolResult(success=True, result={"safe": safe, "reason": reason})
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


def tool_prioritize_actions(tasks: List[str]) -> ActionToolResult:
    """行动优先级排序"""
    try:
        from action_system import ActionSystem
        system = ActionSystem()
        prioritized = system.prioritize(tasks)
        return ActionToolResult(success=True, result={"ordered": prioritized})
    except Exception as e:
        return ActionToolResult(success=False, error=str(e))


ACTION_TOOLS = {
    "plan_action": {"fn": tool_plan_action, "params": ["task", "context"]},
    "execute_action": {"fn": tool_execute_action, "params": ["action_id"]},
    "log_action": {"fn": tool_log_action, "params": ["action", "outcome"]},
    "get_next_action": {"fn": tool_get_next_action, "params": ["priority"]},
    "check_security": {"fn": tool_check_security, "params": ["action"]},
    "prioritize_actions": {"fn": tool_prioritize_actions, "params": ["tasks"]},
}

__all__ = ["ActionToolResult", "ACTION_TOOLS"]
