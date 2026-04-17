#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openclaw_hooks.py — OpenClaw 风格 Hook 系统

Hook 事件（借鉴 OpenClaw）：
1. before_model_resolve  — session 前，覆盖 provider/model
2. before_prompt_build  — session 后，注入 prependContext
3. before_agent_reply  — LLM 调用前，接管 turn
4. before/after_tool_call — 工具调用前后
5. before/after_compaction — 压缩前后
6. agent_end            — 完成时，检查 message list
"""

from __future__ import annotations
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import json

from judgment.logging_config import get_logger
log = get_logger("juhuo.openclaw_hooks")


class HookEvent(Enum):
    """Hook 事件类型"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    BEFORE_MODEL_RESOLVE = "before_model_resolve"
    AFTER_MODEL_RESOLVE = "after_model_resolve"
    BEFORE_PROMPT_BUILD = "before_prompt_build"
    AFTER_PROMPT_BUILD = "after_prompt_build"
    BEFORE_AGENT_REPLY = "before_agent_reply"
    AFTER_AGENT_REPLY = "after_agent_reply"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_COMPACTION = "before_compaction"
    AFTER_COMPACTION = "after_compaction"
    BEFORE_JUDGMENT = "before_judgment"
    AFTER_JUDGMENT = "after_judgment"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENDING = "message_sending"
    MESSAGE_SENT = "message_sent"


@dataclass
class HookContext:
    event: HookEvent
    session_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    event: HookEvent
    handled: bool = False
    override: Any = None
    inject: Dict[str, Any] = None
    blocked: bool = False
    block_reason: str = ""
    modified: bool = False


class Hook(ABC):
    def __init__(self, name: str, events: Set[HookEvent], priority: int = 100):
        self.name = name
        self.events = events
        self.priority = priority
    
    @abstractmethod
    def execute(self, ctx: HookContext) -> HookResult:
        pass


class HookRegistry:
    """Hook 注册表（OpenClaw 风格）"""
    
    def __init__(self):
        self.hooks: Dict[HookEvent, List[Hook]] = {e: [] for e in HookEvent}
        self._enabled = True
    
    def register(self, hook: Hook) -> None:
        for event in hook.events:
            if event not in self.hooks:
                self.hooks[event] = []
            if hook not in self.hooks[event]:
                self.hooks[event].append(hook)
        for event in self.hooks:
            self.hooks[event].sort(key=lambda h: -h.priority)
        log.info(f"Registered hook: {hook.name}")
    
    def fire(self, event: HookEvent, ctx: HookContext = None) -> HookResult:
        if not self._enabled:
            return HookResult(event=event)
        if ctx is None:
            ctx = HookContext(event=event)
        
        result = HookResult(event=event)
        for hook in self.hooks.get(event, []):
            try:
                hr = hook.execute(ctx)
                if hr.blocked:
                    result.blocked = True
                    result.block_reason = hr.block_reason
                    return result
                if hr.handled:
                    result.handled = True
                    result.override = hr.override
                    return result
                if hr.modified:
                    result.modified = True
                if hr.inject:
                    if result.inject is None:
                        result.inject = {}
                    result.inject.update(hr.inject)
            except Exception as e:
                log.error(f"Hook {hook.name} error: {e}")
        return result


class DangerousToolBlocker(Hook):
    """危险工具阻断器"""
    def __init__(self):
        super().__init__("dangerous_blocker", {HookEvent.BEFORE_TOOL_CALL}, 200)
        self.patterns = ["rm -rf", "drop table", "truncate", "delete --", "format", "shutdown"]
    
    def execute(self, ctx: HookContext) -> HookResult:
        args = ctx.data.get("arguments", {})
        args_str = json.dumps(args).lower()
        for p in self.patterns:
            if p in args_str:
                return HookResult(ctx.event, blocked=True, block_reason=f"危险: {p}")
        return HookResult(ctx.event)


class CompactionReminder(Hook):
    """压缩提醒（OpenClaw 启发）"""
    def __init__(self, threshold: int = 15000):
        super().__init__("compaction_reminder", {HookEvent.BEFORE_COMPACTION}, 50)
        self.threshold = threshold
    
    def execute(self, ctx: HookContext) -> HookResult:
        tokens = ctx.data.get("token_count", 0)
        if tokens > self.threshold:
            return HookResult(ctx.event, inject={"reminder": "请保存关键笔记到 memory/"})
        return HookResult(ctx.event)


class ModelFailover(Hook):
    """Model 两阶段降级"""
    def __init__(self, primary: str, fallback: str, emergency: str):
        super().__init__("model_failover", {HookEvent.BEFORE_MODEL_RESOLVE}, 10)
        self.primary = primary
        self.fallback = fallback
        self.emergency = emergency
        self.count = 0
    
    def execute(self, ctx: HookContext) -> HookResult:
        if "error" in ctx.data.get("last_error", "").lower():
            self.count += 1
            if self.count == 1:
                return HookResult(ctx.event, handled=True, override=self.fallback)
            elif self.count >= 2:
                return HookResult(ctx.event, handled=True, override=self.emergency)
        return HookResult(ctx.event)


# 全局注册表
_registry: Optional[HookRegistry] = None

def get_hook_registry() -> HookRegistry:
    global _registry
    if _registry is None:
        _registry = HookRegistry()
        _registry.register(DangerousToolBlocker())
        _registry.register(CompactionReminder())
    return _registry


def fire_hook(event: HookEvent, **kwargs) -> HookResult:
    ctx = HookContext(event=event, data=kwargs)
    return get_hook_registry().fire(event, ctx)


if __name__ == "__main__":
    registry = get_hook_registry()
    ctx = HookContext(event=HookEvent.BEFORE_TOOL_CALL, data={"arguments": {"cmd": "rm -rf /"}})
    result = registry.fire(HookEvent.BEFORE_TOOL_CALL, ctx)
    print(f"Blocked: {result.blocked}, Reason: {result.block_reason}")
