#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
formatter.py — 输出格式化工具

集成来源：conversation_formatter → output_system/
设计原则：
- 对齐 judgment/priority_output.py 的 Priority 枚举（P0-P4）
- 三种格式：brief / full / structured

使用方式：
    from output_system.formatter import OutputFormatter, format_brief, format_full

    fmt = OutputFormatter()
    fmt.add("磁盘满", Priority.CRITICAL)
    fmt.add("建议加索引", Priority.LOW)
    print(fmt.brief())   # 只输出 P0+P1
    print(fmt.full())    # 全部输出
"""

import json
from datetime import datetime
from typing import List, Optional

from judgment.priority_output import Priority, PrioritizedItem, format_output


class OutputFormatter:
    """
    分级输出格式化器

    API：
        add(content, priority, source=None)
        brief()  — P0+P1
        full()   — 全部
        structured()  — JSON
        count_by_priority() -> Dict[str, int]
    """

    def __init__(self, min_level: Optional[Priority] = None):
        # min_level=None 表示全部，0=全部，P0=只P0，P1=只P0+P1
        self.min_level = min_level
        self._items: List[PrioritizedItem] = []

    def add(self, content: str, priority: Priority, source: Optional[str] = None):
        """添加消息"""
        self._items.append(PrioritizedItem(
            priority=priority, content=content, source=source
        ))

    def _filtered(self, max_priority: int) -> List[PrioritizedItem]:
        """返回 <= max_priority 的项"""
        return [i for i in self._items if int(i.priority) <= max_priority]

    def brief(self) -> str:
        """brief — 只输出 P0+P1"""
        items = self._filtered(1)
        if not items:
            return "✅ 无关键问题"
        return "\n".join(format_output(i.content, i.priority, i.source)
                          for i in sorted(items, key=lambda x: x.priority))

    def full(self) -> str:
        """full — 完整输出"""
        if not self._items:
            return "✅ 无问题"
        return "\n".join(format_output(i.content, i.priority, i.source)
                          for i in sorted(self._items, key=lambda x: x.priority))

    def structured(self) -> str:
        """structured — JSON 格式"""
        by_priority: dict = {p.name: [] for p in Priority}
        for item in self._items:
            by_priority[item.priority.name].append({
                "content": item.content,
                "source": item.source,
                "timestamp": item.timestamp.isoformat(),
            })
        output = {
            "generated_at": datetime.now().isoformat(),
            "total": len(self._items),
            "by_priority": {p.name: len(by_priority[p.name]) for p in Priority},
            "messages": by_priority,
        }
        return json.dumps(output, ensure_ascii=False, indent=2)

    def count_by_priority(self) -> dict:
        return {p.name: sum(1 for i in self._items if i.priority == p)
                for p in Priority}

    def clear(self):
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


# ---- 快捷函数 ----

def format_brief(items: List[PrioritizedItem]) -> str:
    filtered = [i for i in items if int(i.priority) <= 1]
    return "\n".join(format_output(i.content, i.priority, i.source)
                     for i in sorted(filtered, key=lambda x: x.priority))


def format_full(items: List[PrioritizedItem]) -> str:
    return "\n".join(format_output(i.content, i.priority, i.source)
                     for i in sorted(items, key=lambda x: x.priority))


def format_structured(items: List[PrioritizedItem]) -> str:
    fmt = OutputFormatter()
    for item in items:
        fmt.add(item.content, item.priority, item.source)
    return fmt.structured()
