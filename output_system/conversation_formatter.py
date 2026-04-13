#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conversation_formatter.py — 对话格式化，P0-P4 分级输出

集成来源：conversation_formatter → output_system/
设计原则：
- 输出更有层次，重要信息不被淹没
- P0: 安全/数据丢失警告
- P1: 性能/错误处理建议
- P2: 可读性/重复代码
- P3: 优化建议

使用方式：
    from output_system.conversation_formatter import Priority, ConversationFormatter

    fmt = ConversationFormatter()
    fmt.add("磁盘满了", Priority.CRITICAL)
    fmt.add("建议加索引", Priority.LOW)
    for line in fmt.format():
        print(line)

    # 或独立使用
    from conversation_formatter import Priority
    print(f"{Priority.label(Priority.HIGH)} 消息内容")
"""
from enum import IntEnum
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


class Priority(IntEnum):
    """对话优先级枚举"""
    CRITICAL = 0   # P0：安全/数据丢失
    HIGH = 1       # P1：性能/错误
    MEDIUM = 2     # P2：可读性
    LOW = 3         # P3：优化
    TRIVIAL = 4   # P4：低优先级

    @staticmethod
    def label(p: "Priority") -> str:
        return ["🚨 P0", "⚠️ P1", "📝 P2", "💡 P3", "  P4"][int(p)]

    @staticmethod
    def desc(p: "Priority") -> str:
        return [
            "安全/数据丢失",
            "性能/错误",
            "可读性/重复",
            "优化建议",
            "低优先级"
        ][int(p)]


@dataclass
class FormattedLine:
    priority: Priority
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None

    def render(self) -> str:
        src = f"[{self.source}] " if self.source else ""
        return f"{Priority.label(self.priority)} {src}{self.content}"


class ConversationFormatter:
    """对话格式化器，按优先级聚合和排序"""

    def __init__(self, min_priority: Priority = Priority.TRIVIAL):
        self.min_priority = min_priority
        self._lines: List[FormattedLine] = []

    def add(self, content: str, priority: Priority,
            source: Optional[str] = None):
        """添加一行，低于 min_priority 的被忽略"""
        if priority <= self.min_priority:
            self._lines.append(FormattedLine(
                priority=priority,
                content=content,
                source=source
            ))

    def format(self) -> List[str]:
        """按优先级排序输出"""
        self._lines.sort(key=lambda x: (x.priority, x.timestamp))
        return [line.render() for line in self._lines]

    def clear(self):
        self._lines.clear()

    def __len__(self):
        return len(self._lines)
