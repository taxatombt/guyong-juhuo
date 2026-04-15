#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json as _json, hashlib

HANDOVER_PREFIX = (
    "You are another language model taking over this conversation.\n"
    "The previous context has been compacted into the sections below.\n"
    "Read carefully - this is the ONLY record of what happened before."
)

@dataclass
class CompactionEntry:
    resolved: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    system_notes: List[str] = field(default_factory=list)
    hash: str = ""

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
        return "\n\n".join(sections) if sections else ""

    def to_document(self) -> str:
        body = self.to_text()
        return HANDOVER_PREFIX + ("\n\n" + body if body else "")

    @staticmethod
    def compute_hash(obj: Dict) -> str:
        return hashlib.sha256(_json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]

class Compact:
    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self._history: List[CompactionEntry] = []

    def compact(self, resolved=None, pending=None, key_decisions=None, system=None):
        resolved = resolved or []
        pending = pending or []
        key_decisions = key_decisions or []
        system = system or []
        entry = CompactionEntry(
            resolved=resolved, pending=pending,
            key_decisions=key_decisions, system_notes=system,
            hash=CompactionEntry.compute_hash({"r": resolved, "p": pending,
                                              "k": key_decisions, "s": system})
        )
        self._history.append(entry)
        if len(self._history) > self.max_entries:
            self._history = self._history[-self.max_entries:]
        return entry.to_document()

    def merge_history(self, keep_recent: int = 5) -> CompactionEntry:
        recent = self._history[-keep_recent:] if len(self._history) >= keep_recent else self._history
        seen = set()
        def dedup(lst): return [x for x in lst if not (x in seen or seen.add(x))]
        return CompactionEntry(
            resolved=dedup([x for e in recent for x in e.resolved]),
            pending=dedup([x for e in recent for x in e.pending]),
            key_decisions=dedup([x for e in recent for x in e.key_decisions]),
            system_notes=dedup([x for e in recent for x in e.system_notes]),
        )

if __name__ == "__main__":
    c = Compact()
    doc = c.compact(
        resolved=["user wants flutter app", "decided on riverpod state management"],
        pending=["waiting for design preferences"],
        key_decisions=["use minimax model"],
        system=["model MiniMax-M2.7", "session token at 65 percent"]
    )
    print(doc)