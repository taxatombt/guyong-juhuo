#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
perception_tools.py — Perception 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class PerceptionToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_filter_attention(content: str, source: str = "unknown") -> PerceptionToolResult:
    """注意力过滤"""
    try:
        from perception import AttentionFilter, IncomingMessage
        filter_ = AttentionFilter()
        msg = IncomingMessage(content=content, source=source)
        result = filter_.filter(msg)
        return PerceptionToolResult(success=True, result={
            "score": result.score,
            "passed": result.passed,
            "reason": result.reason
        })
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_extract_pdf(file_path: str) -> PerceptionToolResult:
    """PDF内容提取"""
    try:
        from perception import extract_pdf_to_judgment_input
        result = extract_pdf_to_judgment_input(file_path)
        return PerceptionToolResult(success=True, result={"blocks": len(result.blocks), "text": result.text[:500]})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_extract_web(url: str) -> PerceptionToolResult:
    """网页内容提取"""
    try:
        from perception import extract_web_to_judgment_input
        result = extract_web_to_judgment_input(url)
        return PerceptionToolResult(success=True, result={"blocks": len(result.blocks), "title": result.title})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_extract_rss(feed_url: str, limit: int = 10) -> PerceptionToolResult:
    """RSS内容提取"""
    try:
        from perception import extract_rss_to_judgment_input
        result = extract_rss_to_judgment_input(feed_url, limit)
        return PerceptionToolResult(success=True, result={"count": len(result.items)})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_fetch_emails(folder: str = "INBOX", limit: int = 10) -> PerceptionToolResult:
    """邮件获取"""
    try:
        from perception import fetch_inbox_to_judgment_input
        result = fetch_inbox_to_judgment_input(folder, limit)
        return PerceptionToolResult(success=True, result={"count": len(result.messages)})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_get_attention_items(status: str = "pending") -> PerceptionToolResult:
    """获取待处理注意力项"""
    try:
        from perception import AttentionFilter
        filter_ = AttentionFilter()
        items = filter_.get_items(status)
        return PerceptionToolResult(success=True, result={"count": len(items), "items": [i.to_dict() for i in items]})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


def tool_score_importance(content: str, context: Optional[Dict] = None) -> PerceptionToolResult:
    """重要性评分"""
    try:
        from perception import AttentionFilter, IncomingMessage
        filter_ = AttentionFilter()
        msg = IncomingMessage(content=content, source="analysis")
        score = filter_.score_importance(msg, context or {})
        return PerceptionToolResult(success=True, result={"score": score})
    except Exception as e:
        return PerceptionToolResult(success=False, error=str(e))


PERCEPTION_TOOLS = {
    "filter_attention": {"fn": tool_filter_attention, "params": ["content", "source"]},
    "extract_pdf": {"fn": tool_extract_pdf, "params": ["file_path"]},
    "extract_web": {"fn": tool_extract_web, "params": ["url"]},
    "extract_rss": {"fn": tool_extract_rss, "params": ["feed_url", "limit"]},
    "fetch_emails": {"fn": tool_fetch_emails, "params": ["folder", "limit"]},
    "get_attention_items": {"fn": tool_get_attention_items, "params": ["status"]},
    "score_importance": {"fn": tool_score_importance, "params": ["content", "context"]},
}

__all__ = ["PerceptionToolResult", "PERCEPTION_TOOLS"]
