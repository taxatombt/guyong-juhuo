#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TurnDiffTracker — 决策影响追踪
追踪每个决策（turn）→ 触发了哪些文件变更 → 因果推断
"""

from __future__ import annotations
import hashlib, json, time, difflib, re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

TRACKER_FILE = Path(__file__).parent / "turn_diffs.json"

@dataclass
class FileChange:
    path: str
    change_type: str
    before_hash: Optional[str]
    after_hash: Optional[str]
    diff_preview: str
    tool: str

@dataclass
class TurnDiff:
    turn_id: str
    timestamp: float
    decision_summary: str
    changes: List[FileChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "decision_summary": self.decision_summary,
            "changes": [asdict(c) for c in self.changes],
        }

def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def _compute_diff(before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True), n=3)
    return "".join(list(diff)[:20])[:300]

class TurnDiffTracker:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or TRACKER_FILE
        self._turn_diffs: Dict[str, TurnDiff] = {}
        self._current_turn_id: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self._turn_diffs = {k: self._dict_to_turn(v) for k, v in data.items()}
            except (json.JSONDecodeError, KeyError):
                self._turn_diffs = {}

    def _save(self) -> None:
        data = {k: v.to_dict() for k, v in self._turn_diffs.items()}
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _dict_to_turn(self, d: dict) -> TurnDiff:
        return TurnDiff(
            turn_id=d["turn_id"],
            timestamp=d["timestamp"],
            decision_summary=d["decision_summary"],
            changes=[FileChange(**c) for c in d.get("changes", [])],
        )

    def begin_turn(self, turn_id: str, decision_summary: str = "") -> None:
        self._current_turn_id = turn_id
        if turn_id not in self._turn_diffs:
            self._turn_diffs[turn_id] = TurnDiff(
                turn_id=turn_id, timestamp=time.time(),
                decision_summary=decision_summary, changes=[])

    def update_decision_summary(self, summary: str) -> None:
        if self._current_turn_id and self._current_turn_id in self._turn_diffs:
            self._turn_diffs[self._current_turn_id].decision_summary = summary

    def on_tool_call(self, tool: str, args: Dict[str, Any], result: Any) -> Optional[FileChange]:
        if self._current_turn_id is None:
            return None
        turn = self._turn_diffs[self._current_turn_id]
        change: Optional[FileChange] = None

        # write_file / Write
        if tool in ("write_file", "Write"):
            path = str(args.get("file_path") or args.get("path", ""))
            content = str(args.get("content") or "")
            if not path:
                return None
            before_hash = None
            after_hash = _file_hash(content)
            change_type = "created"
            if Path(path).exists():
                before_hash = _file_hash(Path(path).read_text(encoding="utf-8"))
                change_type = "modified"
            change = FileChange(
                path=path, change_type=change_type,
                before_hash=before_hash, after_hash=after_hash,
                diff_preview=self._diff_for_path(path, content) if before_hash else "",
                tool=tool)

        # edit_file / Edit
        elif tool in ("edit_file", "Edit"):
            path = str(args.get("file_path") or args.get("path", ""))
            new_text = str(args.get("new_text") or "")
            if not path or not Path(path).exists():
                return None
            before_content = Path(path).read_text(encoding="utf-8")
            change = FileChange(
                path=path, change_type="modified",
                before_hash=_file_hash(before_content),
                after_hash=_file_hash(before_content),
                diff_preview=_compute_diff(before_content, new_text)[:300],
                tool=tool)

        # Execute / Bash
        elif tool in ("execute_shell_command", "Execute", "Bash"):
            result_str = str(result) if result else ""
            paths = self._extract_paths(result_str)
            changes = []
            for p in paths:
                if Path(p).exists():
                    changes.append(FileChange(
                        path=p, change_type="modified",
                        before_hash=None,
                        after_hash=_file_hash(Path(p).read_text(encoding="utf-8")),
                        diff_preview="[from_execute]", tool=tool))
            for c in changes:
                turn.changes.append(c)
            return changes[0] if changes else None

        if change:
            turn.changes.append(change)
        return change

    def _diff_for_path(self, path: str, new_content: str) -> str:
        if not Path(path).exists():
            return ""
        return _compute_diff(Path(path).read_text(encoding="utf-8"), new_content)[:300]

    def _extract_paths(self, text: str) -> List[str]:
        pattern = r"(?:[A-Za-z]:\\[\w\\./-]+|/[\w/.-]+|\./[\w/.-]+|[\w-]+\.[a-zA-Z]{2,6})"
        return list(set(re.findall(pattern, text)))[:5]

    def get_decision_impact(self, turn_id: str) -> List[FileChange]:
        turn = self._turn_diffs.get(turn_id)
        return turn.changes if turn else []

    def get_all_turn_ids(self) -> List[str]:
        return list(self._turn_diffs.keys())

    def get_file_history(self, file_path: str) -> List[Dict[str, Any]]:
        history = []
        for turn in self._turn_diffs.values():
            for change in turn.changes:
                if change.path == file_path:
                    history.append({
                        "turn_id": turn.turn_id, "timestamp": turn.timestamp,
                        "change_type": change.change_type, "tool": change.tool,
                        "decision_summary": turn.decision_summary})
        return history

    def flush(self) -> None:
        self._save()

if __name__ == "__main__":
    tracker = TurnDiffTracker()
    tracker.begin_turn("turn_1", decision_summary="写九九乘法表")
    tracker.on_tool_call(
        tool="write_file",
        args={"file_path": "E:/tmp/multiply.py", "content": "for i in range(1,10):\n    print(i)"},
        result={})
    changes = tracker.get_decision_impact("turn_1")
    print(f"turn_1 影响 {len(changes)} 个文件")
    for c in changes:
        print(f"  [{c.change_type}] {c.path}")
    tracker.flush()
    print("Done")
