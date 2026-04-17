#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment_tools.py — Judgment 子系统工具

十维判断系统暴露的工具接口
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from judgment import (
    check10d,
    route,
    format_report,
    format_structured,
    Dimension,
    calculate_dimension_confidence,
    get_dynamic_weights,
    get_task_complexity,
    detect_task_types,
    metacognitive_review,
    metacognitive_self_check,
    get_bias_checklist,
)
from judgment.error_classifier import ErrorClassifier


@dataclass
class JudgmentToolResult:
    """判断工具结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_check10d(
    task_text: str,
    agent_profile: Optional[Dict] = None,
    complexity: str = "auto"
) -> JudgmentToolResult:
    """十维判断分析"""
    try:
        result = check10d(task_text, agent_profile, complexity)
        return JudgmentToolResult(success=True, result=result)
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_verify_judgment(
    judgment_result: Dict,
    user_verdict: str,
    user_feedback: Optional[str] = None
) -> JudgmentToolResult:
    """验证判断结果"""
    try:
        from judgment.verifier import verify_judgment
        result = verify_judgment(judgment_result, user_verdict, user_feedback)
        return JudgmentToolResult(success=True, result=result)
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_get_dimension_confidence(
    dimension: str,
    context: Optional[Dict] = None
) -> JudgmentToolResult:
    """获取维度置信度"""
    try:
        dim = Dimension(dimension)
        confidence = calculate_dimension_confidence(dim, context or {})
        return JudgmentToolResult(success=True, result={
            "dimension": dimension,
            "confidence": confidence.value,
            "reason": confidence.reason
        })
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_get_dynamic_weights(
    task_text: str,
    agent_profile: Optional[Dict] = None
) -> JudgmentToolResult:
    """获取动态权重"""
    try:
        weights = get_dynamic_weights(task_text, agent_profile)
        complexity = get_task_complexity(task_text)
        task_types = detect_task_types(task_text)
        return JudgmentToolResult(success=True, result={
            "weights": weights.to_dict(),
            "complexity": complexity,
            "task_types": task_types
        })
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_metacognitive_review(
    judgment_result: Dict,
    self_correction: bool = True
) -> JudgmentToolResult:
    """元认知审查"""
    try:
        if self_correction:
            result = metacognitive_self_check(judgment_result)
        else:
            result = metacognitive_review(judgment_result)
        return JudgmentToolResult(success=True, result=result)
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_route(task_text: str) -> JudgmentToolResult:
    """路由判断"""
    try:
        path = route(task_text)
        return JudgmentToolResult(success=True, result={
            "path": path.value,
            "description": path.description
        })
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_classify_error(error: Any) -> JudgmentToolResult:
    """API错误5分类"""
    try:
        classifier = ErrorClassifier()
        result = classifier.classify(error)
        return JudgmentToolResult(success=True, result={
            "error_type": result.error_type.name,
            "strategy": result.strategy.name,
            "retry_after": result.retry_after,
            "detail": result.detail
        })
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_get_bias_checklist() -> JudgmentToolResult:
    """认知偏差检查清单"""
    try:
        checklist = get_bias_checklist()
        return JudgmentToolResult(success=True, result=checklist)
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


def tool_format_judgment(
    judgment_result: Dict,
    format_type: str = "text"
) -> JudgmentToolResult:
    """格式化判断输出"""
    try:
        if format_type == "text":
            result = format_report(judgment_result)
        elif format_type == "structured":
            result = format_structured(judgment_result)
        else:
            result = judgment_result
        return JudgmentToolResult(success=True, result=result)
    except Exception as e:
        return JudgmentToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# 工具注册表
# ═══════════════════════════════════════════════════════════════════════════

JUDGMENT_TOOLS = {
    "check10d": {
        "name": "check10d",
        "description": "十维判断分析",
        "category": "judgment",
        "fn": tool_check10d,
        "params": {
            "task_text": {"type": "string", "required": True},
            "agent_profile": {"type": "object", "required": False},
            "complexity": {"type": "string", "required": False, "default": "auto"}
        }
    },
    "verify_judgment": {
        "name": "verify_judgment",
        "description": "验证判断结果",
        "category": "judgment",
        "fn": tool_verify_judgment,
        "params": {
            "judgment_result": {"type": "object", "required": True},
            "user_verdict": {"type": "string", "required": True},
            "user_feedback": {"type": "string", "required": False}
        }
    },
    "get_dimension_confidence": {
        "name": "get_dimension_confidence",
        "description": "获取维度置信度",
        "category": "judgment",
        "fn": tool_get_dimension_confidence,
        "params": {
            "dimension": {"type": "string", "required": True},
            "context": {"type": "object", "required": False}
        }
    },
    "get_dynamic_weights": {
        "name": "get_dynamic_weights",
        "description": "获取动态权重",
        "category": "judgment",
        "fn": tool_get_dynamic_weights,
        "params": {
            "task_text": {"type": "string", "required": True},
            "agent_profile": {"type": "object", "required": False}
        }
    },
    "metacognitive_review": {
        "name": "metacognitive_review",
        "description": "元认知审查",
        "category": "judgment",
        "fn": tool_metacognitive_review,
        "params": {
            "judgment_result": {"type": "object", "required": True},
            "self_correction": {"type": "boolean", "required": False, "default": True}
        }
    },
    "route": {
        "name": "route",
        "description": "路由判断",
        "category": "judgment",
        "fn": tool_route,
        "params": {
            "task_text": {"type": "string", "required": True}
        }
    },
    "classify_error": {
        "name": "classify_error",
        "description": "API错误5分类",
        "category": "judgment",
        "fn": tool_classify_error,
        "params": {
            "error": {"type": "any", "required": True}
        }
    },
    "get_bias_checklist": {
        "name": "get_bias_checklist",
        "description": "认知偏差检查清单",
        "category": "judgment",
        "fn": tool_get_bias_checklist,
        "params": {}
    },
    "format_judgment": {
        "name": "format_judgment",
        "description": "格式化判断输出",
        "category": "judgment",
        "fn": tool_format_judgment,
        "params": {
            "judgment_result": {"type": "object", "required": True},
            "format_type": {"type": "string", "required": False, "default": "text"}
        }
    },
}


__all__ = [
    "JudgmentToolResult",
    "tool_check10d",
    "tool_verify_judgment",
    "tool_get_dimension_confidence",
    "tool_get_dynamic_weights",
    "tool_metacognitive_review",
    "tool_route",
    "tool_classify_error",
    "tool_get_bias_checklist",
    "tool_format_judgment",
    "JUDGMENT_TOOLS",
]
