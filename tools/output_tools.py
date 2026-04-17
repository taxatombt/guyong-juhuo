#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
output_tools.py — Output 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class OutputToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_format_output(content: str, style: str = "default") -> OutputToolResult:
    """格式化输出"""
    try:
        from output_system import format_output
        result = format_output(content, style)
        return OutputToolResult(success=True, result={"formatted": result})
    except Exception as e:
        return OutputToolResult(success=False, error=str(e))


def tool_apply_priority(content: str, priority: int = 3) -> OutputToolResult:
    """应用优先级"""
    try:
        from output_system import OutputSystem
        system = OutputSystem()
        result = system.apply_priority(content, priority)
        return OutputToolResult(success=True, result={"priority": priority, "output": result})
    except Exception as e:
        return OutputToolResult(success=False, error=str(e))


def tool_should_respond(context: Dict) -> OutputToolResult:
    """判断是否应该回应"""
    try:
        from output_system import OutputSystem
        system = OutputSystem()
        should, reason = system.should_respond(context)
        return OutputToolResult(success=True, result={"should": should, "reason": reason})
    except Exception as e:
        return OutputToolResult(success=False, error=str(e))


def tool_get_conversation_format(conversation_type: str = "general") -> OutputToolResult:
    """获取对话格式"""
    try:
        from output_system import get_conversation_format
        result = get_conversation_format(conversation_type)
        return OutputToolResult(success=True, result={"format": result})
    except Exception as e:
        return OutputToolResult(success=False, error=str(e))


OUTPUT_TOOLS = {
    "format_output": {"fn": tool_format_output, "params": ["content", "style"]},
    "apply_priority": {"fn": tool_apply_priority, "params": ["content", "priority"]},
    "should_respond": {"fn": tool_should_respond, "params": ["context"]},
    "get_conversation_format": {"fn": tool_get_conversation_format, "params": ["conversation_type"]},
}

__all__ = ["OutputToolResult", "OUTPUT_TOOLS"]
