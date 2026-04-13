#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insight_tracker.py — token/会话/工具使用追踪，记录到 judgment/

集成来源：ECC Codex insight_tracker → judgment/
设计原则：
- 追踪每个会话的 token 消耗、工具调用次数、API 错误率
- 不只是记录数字，是形成 insight：成本是否合理？哪类工具最贵？
- 定期输出 session insight report

使用方式：
    from judgment.insight_tracker import InsightTracker, TokenSnapshot

    tracker = InsightTracker()
    tracker.record_input(1200)
    tracker.record_output(4500)
    tracker.record_tool("read_file", duration=0.3)
    tracker.record_error("rate_limit")

    report = tracker.summary()
    print(report)
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import json
from pathlib import Path


class EventType(Enum):
    INPUT_TOKEN = auto()
    OUTPUT_TOKEN = auto()
    TOOL_CALL = auto()
    ERROR = auto()
    LATENCY = auto()


@dataclass
class Event:
    event_type: EventType
    value: float
    label: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "type": self.event_type.name,
            "value": self.value,
            "label": self.label,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SessionInsight:
    """会话洞察报告"""
    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0