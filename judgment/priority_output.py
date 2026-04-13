#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
priority_output.py — P0-P4 分级格式化输出

集成来源：conversation_formatter → judgment/ → output_system/
设计原则：
- 重要信息不被淹没，输出有层次
- P0 安全/数据丢失 > P1 性能/错误 > P2 可读性 > P3 优化 > P4 建议

使用方式：
    from judgment.priority_output import Priority, format_output, PriorityOutput

    # 独立函数
    format_output("磁盘空间不足", Priority.CRITICAL)  # → "🚨 P0 磁盘空间不足"

    # 类（可注入到现有系统）
    printer = PriorityOutput(min_level=Priority.MEDIUM)
    printer.add("建议加索引", Priority.LOW)
    printer.add("JSON语法错误", Priority.HIGH)
    printer.flush()  # 按优先级排序输出
"""
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


class Priority(IntEnum):
    """P0-P4 优先级，数字越小越紧急"""
    CRITICAL = 0   # P0：安全/数据丢失，必须立即处理
    HIGH = 1       # P1：性能/错误处理建议
    MEDIUM = 2     # P2：可读性/重复代码
    LOW = 3        # P3：优化建议
    TRIVIAL = 4   # P4：低优先级提示

    @staticmethod
    def label(p: "Priority") -> str:
        labels = ["🚨 P0", "⚠️ P1", "📝 P2", "💡 P3", "  P4"]
        return labels[int(p)] if isinstance(p, Priority) else labels[p]

    @staticmethod
    def desc(p: "Priority") -> str:
        descs = [
            "安全/数据丢失",
            "性能/错误处理",
            "可读性/重复",
            "优化建议",
            "低优先级提示"
        ]
        return descs[int(p)] if isinstance(p, Priority) else descs[p]


@dataclass
class PrioritizedItem:
    priority: Priority
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None


def format_output(content: str, priority: Priority, source: Optional[str] = None) -> str:
    """格式化单条输出，带优先级标签"""
    label = Priority.label(priority)
    prefix = f"[{source}] " if source else ""
    return f"{label} {prefix}{content}"


class PriorityOutput:
    """优先级输出聚合器，按优先级排序输出"""

    def __init__(self, min_level: Priority = Priority.TRIVIAL):
        self.min_level = min_level
        self._items: List[PrioritizedItem] = []

    def add(self, content: str, priority: Priority, source: Optional[str] = None):
        if priority <= self.min_level:
            self._items.append(PrioritizedItem(
                priority=priority,
                content=content,
                source=source
            ))

    def flush(self) -> List[str]:
        """按优先级排序并输出，返回格式化字符串列表"""
        self._items.sort(key=lambda x: (x.priority, x.timestamp))
        return [format_output(item.content, item.priority, item.source)
                for item in self._items]

    def clear(self):
        self._items.clear()


# 快捷函数
def P0(content: str, source: Optional[str] = None) -> str:
    return format_output(content, Priority.CRITICAL, source)

def P1(content: str, source: Optional[str] = None) -> str:
    return format_output(content, Priority.HIGH, source)

def P2(content: str, source: Optional[str] = None) -> str:
    return format_output(content, Priority.MEDIUM, source)

def P3(content: str, source: Optional[str] = None) -> str:
    return format_output(content, Priority.LOW, source)

def P4(content: str, source: Optional[str] = None) -> str:
    return format_output(content, Priority.TRIVIAL, source)
