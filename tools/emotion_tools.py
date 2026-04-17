#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emotion_tools.py — Emotion & Curiosity 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class EmotionToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_analyze_emotion(text: str) -> EmotionToolResult:
    """情绪分析"""
    try:
        from emotion_system import EmotionSystem
        system = EmotionSystem()
        signals = system.analyze_text(text)
        return EmotionToolResult(success=True, result={
            "signals": [s.to_dict() for s in signals],
            "dominant": signals[0].to_dict() if signals else None
        })
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_get_pad_scores(text: str) -> EmotionToolResult:
    """获取PAD情绪评分"""
    try:
        from emotion_system import EmotionSystem
        system = EmotionSystem()
        pad = system.get_pad_scores(text)
        return EmotionToolResult(success=True, result=pad)
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_get_curiosity_items(limit: int = 5) -> EmotionToolResult:
    """获取好奇心项"""
    try:
        from curiosity import get_top_open
        items = get_top_open(limit)
        return EmotionToolResult(success=True, result={"count": len(items), "items": [i.to_dict() for i in items]})
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_trigger_curiosity(context: Dict) -> EmotionToolResult:
    """触发好奇心"""
    try:
        from curiosity import trigger_from_low_confidence
        item = trigger_from_low_confidence(context)
        return EmotionToolResult(success=True, result=item.to_dict() if item else None)
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_resolve_curiosity(item_id: str, resolution: str) -> EmotionToolResult:
    """解决好奇心"""
    try:
        from curiosity import resolve
        result = resolve(item_id, resolution)
        return EmotionToolResult(success=True, result={"resolved": result})
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_get_daily_curiosity() -> EmotionToolResult:
    """获取每日好奇心列表"""
    try:
        from curiosity import get_daily_list
        items = get_daily_list()
        return EmotionToolResult(success=True, result={"count": len(items), "items": [i.to_dict() for i in items]})
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


def tool_full_curiosity_report() -> EmotionToolResult:
    """完整好奇心报告"""
    try:
        from curiosity import full_report
        report = full_report()
        return EmotionToolResult(success=True, result=report)
    except Exception as e:
        return EmotionToolResult(success=False, error=str(e))


EMOTION_TOOLS = {
    "analyze_emotion": {"fn": tool_analyze_emotion, "params": ["text"]},
    "get_pad_scores": {"fn": tool_get_pad_scores, "params": ["text"]},
    "get_curiosity_items": {"fn": tool_get_curiosity_items, "params": ["limit"]},
    "trigger_curiosity": {"fn": tool_trigger_curiosity, "params": ["context"]},
    "resolve_curiosity": {"fn": tool_resolve_curiosity, "params": ["item_id", "resolution"]},
    "get_daily_curiosity": {"fn": tool_get_daily_curiosity, "params": []},
    "full_curiosity_report": {"fn": tool_full_curiosity_report, "params": []},
}

__all__ = ["EmotionToolResult", "EMOTION_TOOLS"]
