#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
observe_hook.py — 被动工具调用捕获钩子

集成来源：evolver_observer.py → feedback_system/
设计原则：
- 100% 工具调用捕获，不漏，不主动分析
- 5层防护，防止 self-loop（自己观察自己导致无限循环）
- 数据丰富：不只是"对/错"，还有"怎么错的"

数据流：
    工具调用 → observe_hook → feedback_system.record()
                        ↓
               judgment/self_review(主动分析)

使用方式：
    from feedback_system.observe_hook import ObserveHook, should_observe

    hook = ObserveHook()
    hook.on_tool_call("read_file", args, result="ok", duration_ms=12)
    hook.on_tool_call("execute_shell", args, result="fail", error="timeout")
    hook.flush()
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import threading


# ============================================================
# 5层自防：防止 observe_hook 自己observe自己
# ============================================================

# 层1：黑名单关键词（观察这些工具会死循环）
_SELF_OBSERVER_BLACKLIST = {
    "observe_hook",
    "observe",
    "record",
    "_ensure_file",
    "_save",
    "_load",
}

# 层2：结果黑名单（包含这些关键词的结果不记录）
_RESULT_BLACKLIST = {
    "observe_hook.py",
    "_ensure_files",
    "observer_log",
    "feedback_system",
}

# 层3：参数黑名单（参数包含这些词不记录）
_PARAM_BLACKLIST = {
    "observe",
    "should_observe",
    "ObserveHook",
}

# 去重滑动窗口（毫秒）
_DEDUP_WINDOW_MS = 60_000

# 最大缓冲数
_MAX_BUFFER = 10000


@dataclass
class ToolObservation:
    """单次工具调用记录"""
    tool: str
    args: Dict[str, Any]
    result: str  # ok / fail / error
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "args": self.args,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "session": self.session,
        }


def _is_sensitive_key(key: str) -> bool:
    """脱敏：隐藏敏感参数名"""
    sensitive = {"password", "token", "secret", "api_key", "apikey",
                 "auth", "credential", "secret_key", "private_key"}
    return key.lower().strip("_") in sensitive


def _sanitize_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """对参数做脱敏，隐藏敏感值"""
    return {
        k: ("***REDACTED***" if _is_sensitive_key(k) else v)
        for k, v in args.items()
    }


def should_observe(event: Dict[str, Any]) -> bool:
    """
    5层防护判断：这条工具调用该不该被记录

    触发任一条件 → 不记录
    """
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    result = event.get("result", "")

    # 层1：工具名黑名单
    if any(bad in tool_name.lower() for bad in _SELF_OBSERVER_BLACKLIST):
        return False

    # 层2：结果包含敏感词
    if any(bad in str(result) for bad in _RESULT_BLACKLIST):
        return False

    # 层3：参数包含敏感词
    if any(bad in str(tool_input) for bad in _PARAM_BLACKLIST):
        return False

    return True


class ObserveHook:
    """
    被动观察钩子：只记录，不过滤，不分析

    API：
        on_tool_call(tool, args, result=ok, error=None, duration_ms=None)
        flush()  — 强制刷盘
        get_buffer() -> List[ToolObservation]
        close()  — 关闭时刷盘
    """

    def __init__(
        self,
        log_path: str = ".evolver/observer_log.jsonl",
        flush_interval: int = 50,
    ):
        self.log_path = Path(log_path)
        self.flush_interval = flush_interval
        self._buffer: List[ToolObservation] = []
        self._lock = threading.Lock()
        self._counter = 0

    def on_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str = "ok",
        *,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        session: Optional[str] = None,
    ) -> None:
        """记录一次工具调用"""
        event = {"tool_name": tool_name, "tool_input": args, "result": result}
        if not should_observe(event):
            return

        obs = ToolObservation(
            tool=tool_name,
            args=_sanitize_args(args),
            result=result,
            error=error,
            duration_ms=duration_ms,
            session=session,
        )

        with self._lock:
            self._buffer.append(obs)
            self._counter += 1
            if len(self._buffer) >= self.flush_interval:
                self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        """内部刷盘（已持有锁）"""
        if not self._buffer:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            for obs in self._buffer:
                f.write(json.dumps(obs.to_dict(), ensure_ascii=False) + "\n")
        self._buffer.clear()

    def flush(self) -> int:
        """强制刷盘，返回本次写入条数"""
        with self._lock:
            n = len(self._buffer)
            self._flush_unlocked()
            return n

    def get_buffer(self) -> List[ToolObservation]:
        """获取当前缓冲（快照）"""
        with self._lock:
            return list(self._buffer)

    def close(self) -> None:
        """关闭时刷盘"""
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
