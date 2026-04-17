#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session.py — Juhuo Judgment Session

借鉴 OpenClaw Agent Loop：
1. Session 生命周期管理
2. 流式事件（lifecycle/assistant/tool）
3. Queue + Concurrency 控制
4. 与 Hook 系统集成
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json, uuid

from judgment.logging_config import get_logger
from judgment.openclaw_hooks import HookEvent, HookContext, get_hook_registry
log = get_logger("juhuo.session")


class SessionStatus(Enum):
    INIT = "init"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: str
    content: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class JudgmentTurn:
    turn_id: str
    timestamp: str
    input: str
    output: Dict[str, Any]
    tool_calls: List[Dict] = field(default_factory=list)
    error: str = ""


class JudgmentSession:
    """Judgment Session（OpenClaw 启发）"""
    
    def __init__(self, session_id: Optional[str] = None, user_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.user_id = user_id
        self.status = SessionStatus.INIT
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.turns: List[JudgmentTurn] = []
        self.current_turn: Optional[JudgmentTurn] = None
        self.stream_handlers: Dict[str, List[Callable]] = {"lifecycle": [], "assistant": [], "tool": []}
        self._locks: Dict[str, int] = {}
        self.hooks = get_hook_registry()
        log.info(f"Session: {self.session_id}")
    
    def start(self) -> None:
        self.status = SessionStatus.RUNNING
        self._emit("lifecycle", {"event": "start"})
        self.hooks.fire(HookEvent.SESSION_START, session_id=self.session_id)
    
    def end(self, reason: str = "completed") -> None:
        self.status = SessionStatus.COMPLETED if reason == "completed" else SessionStatus.ERROR
        self._emit("lifecycle", {"event": reason})
        self.hooks.fire(HookEvent.SESSION_END, session_id=self.session_id)
    
    def new_turn(self, input_text: str) -> JudgmentTurn:
        self.current_turn = JudgmentTurn(str(uuid.uuid4())[:8], datetime.now().isoformat(), input_text, {})
        return self.current_turn
    
    def end_turn(self, output: Dict, error: str = "") -> None:
        if self.current_turn:
            self.current_turn.output = output
            self.current_turn.error = error
            self.turns.append(self.current_turn)
            self.current_turn = None
    
    def add_tool_call(self, tool: str, args: Dict, result: Any) -> None:
        if self.current_turn:
            self.current_turn.tool_calls.append({"tool": tool, "args": args, "result": result})
    
    def on_stream(self, etype: str, handler: Callable) -> None:
        if etype in self.stream_handlers:
            self.stream_handlers[etype].append(handler)
    
    def _emit(self, etype: str, data: Any) -> None:
        for h in self.stream_handlers.get(etype, []):
            try: h(StreamEvent(etype, data))
            except: pass
    
    def acquire(self, resource: str) -> bool:
        if self._locks.get(resource, 0) >= 3:
            return False
        self._locks[resource] = self._locks.get(resource, 0) + 1
        return True
    
    def release(self, resource: str) -> None:
        if resource in self._locks:
            self._locks[resource] = max(0, self._locks[resource] - 1)
    
    def to_dict(self) -> Dict:
        return {"session_id": self.session_id, "status": self.status.value, "turns": len(self.turns)}
    
    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"meta": self.to_dict(), "turns": [vars(t) for t in self.turns]}, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "JudgmentSession":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = cls(data["meta"]["session_id"])
        s.status = SessionStatus(data["meta"]["status"])
        s.turns = [JudgmentTurn(**t) for t in data.get("turns", [])]
        return s


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, JudgmentSession] = {}
        self._active: Optional[str] = None
    
    def create(self, user_id: str = None) -> JudgmentSession:
        s = JudgmentSession(user_id=user_id)
        self.sessions[s.session_id] = s
        self._active = s.session_id
        return s
    
    def get(self, sid: str) -> Optional[JudgmentSession]:
        return self.sessions.get(sid)
    
    def active(self) -> Optional[JudgmentSession]:
        return self.sessions.get(self._active) if self._active else None
    
    def list(self) -> List[Dict]:
        return [s.to_dict() for s in self.sessions.values()]


# 全局管理器
_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
