#!/usr/bin/env python3
"""生成 compact.py"""
p = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'compact.py')
code = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compact.py - HANDOVER DOCUMENT 格式上下文压缩
来源: weekly report 2026-04-14 / CoPaw workspace_tools/compact.py

HANDOVER DOCUMENT 格式:
- 前导语: "You are another language model..."
- 四段结构: RESOLVED / PENDING / KEY DECISIONS / SYSTEM
- 用于上下文满了时的压缩，保持决策轨迹可追溯
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json, hashlib

# ── HANDOVER DOCUMENT 前导语 ───────────────────────────────────────────

HANDOVER_PREFIX = """You are another language model taking over this conversation.
The previous context has been compacted into the sections below.
Read carefully - this is the ONLY record of what happened before."""

# ── 数据模型 ────────────────────────────────────────────────────────────

@dataclass
class CompactionEntry:
    resolved: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    system_notes: List[str] = field(default_factory=list)
    hash: str = ""  # 内容指纹，检测是否真的有变化

    def to_text(self) -> str:
        sections = []
        if self.resolved:
            sections.append("## RESOLVED\n" + "\n".join(f"- {x}" for x in self.resolved))
        if self.pending:
            sections.append("## PENDING\n" + "\n".join(f"- [ ] {x}" for x in self.pending))
        if self.key_decisions:
            sections.append("## KEY DECISIONS\n" + "\n".join(f"- {x}" for x in self.key_decisions))
        if self.system_notes:
            sections.append("## SYSTEM\n" + "\n".join(f"- {x}" for x in self.system_notes))
        if not sections:
            return ""
        return "\n\n".join(sections)

    def to_document(self) -> str:
        body = self.to_text()
        if not body:
            return HANDOVER_PREFIX
        return f"{HANDOVER_PREFIX}\n\n{body}"

    @staticmethod
    def compute_hash(obj: Dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]

# ── 压缩器 ──────────────────────────────────────────────────────────────

class Compact:
    """
    HANDOVER DOCUMENT 格式的上下文压缩器。

    用法:
        compact = Compact()
        doc = compact.compact(
            resolved=["用户想要Flutter App"],
            pending=["等待用户提供设计偏好"],
            key_decisions=["用Riverpod做状态管理"],
            system=["模型用MiniMax-M2.7"]
        )
        print(doc)
    """
    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self._history: List[CompactionEntry] = []

    def compact(
        self,
        resolved: Optional[List[str]] = None,
        pending: Optional[List[str]] = None,
        key_decisions: Optional[List[str]] = None,
        system: Optional[List[str]] = None,
    ) -> str:
        entry = CompactionEntry(
            resolved=resolved or [],
            pending=pending or [],
            key_decisions=key_decisions or [],
            system_notes=system or [],
            hash=CompactionEntry.compute_hash({
                "r": resolved, "p": pending, "k": key_decisions, "s": system
            })
        )
        self._history.append(entry)
        if len(self._history) > self.max_entries:
            self._history = self._history[-self.max_entries:]
        return entry.to_document()

    def merge_history(self, keep_recent: int = 5) -> CompactionEntry:
        """
        合并历史记录，生成一个综合的 handover document。
        保留最近 keep_recent 条，其余合并。
        """
        recent = self._history[-keep_recent:] if len(self._history) >= keep_recent else self._history
        all_resolved, all_pending, all_decisions, all_system = [], [], [], []
        for e in recent:
            all_resolved.extend(e.resolved)
            all_pending.extend(e.pending)
            all_decisions.extend(e.key_decisions)
            all_system.extend(e.system_notes)
        # 去重保持顺序
        seen = set()
        dedup = lambda lst: [x for x in lst if not (x in seen or seen.add(x))]
        merged = CompactionEntry(
            resolved=ded
</think>
