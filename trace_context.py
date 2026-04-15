# trace_context.py — Juhuo 全链路追踪
# 用途：在 pipeline 的各子系统间传递 trace_id，记录调用链到 causal_memory
# 使用方式：
#     from trace_context import TraceContext, trace_call
#     
#     # 方式1：自动追踪（推荐）
#     result = trace_call("judgment.check10d", lambda: check10d(text))
#     
#     # 方式2：手动上下文管理器
#     with TraceContext("pipeline.run") as ctx:
#         ctx.put("stage", "judgment")
#         ctx.put("input_length", len(text))
#         result = check10d(text)
#         ctx.put("verdict", result.verdict)
#
# 查看追踪：
#     from trace_context import get_current_trace
#     trace = get_current_trace()

from __future__ import annotations
import uuid
import time
import json
import os
from typing import Any, Callable, Dict, Optional
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from functools import wraps

# ─── ContextVar（协程安全）───────────────────────────────────────────────────

_current_trace: ContextVar[Optional["TraceData"]] = ContextVar(
    "_current_trace", default=None
)

_trace_enabled: ContextVar[bool] = ContextVar(
    "_trace_enabled", default=False
)


def is_tracing_enabled() -> bool:
    """检查追踪是否启用（默认关闭，由 trace_call 临时开启）"""
    return _trace_enabled.get() is True


# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class Span:
    """单个调用节点"""
    span_id: str
    name: str
    start_ms: float
    end_ms: Optional[float] = None
    fields: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    children: list = field(default_factory=list)

    def duration_ms(self) -> float:
        if self.end_ms is None:
            return time.time() * 1000 - self.start_ms
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "name": self.name,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": round(self.duration_ms(), 2),
            "fields": self.fields,
            "error": self.error,
            "children": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.children],
        }


@dataclass
class TraceData:
    """完整调用链"""
    trace_id: str
    root_span: Span
    current_span: Span
    started_at: float = field(default_factory=time.time)
    _spans: Dict[str, Span] = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        """在当前 span 记录字段"""
        self.current_span.fields[key] = _serialize(value)

    def set_error(self, error: str) -> None:
        self.current_span.error = error

    def span(self, name: str) -> "SpanContext":
        """在当前 span 下创建子 span"""
        return SpanContext(self, name)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "trace": self.root_span.to_dict(),
        }


class SpanContext:
    """子 span 临时上下文管理器（with TraceContext.span("name") as ctx:）"""
    def __init__(self, trace: TraceData, name: str):
        self._trace = trace
        self._span = Span(
            span_id=_short_id(),
            name=name,
            start_ms=time.time() * 1000,
        )
        self._prev_span = trace.current_span

    def __enter__(self):
        self._trace.current_span.children.append(self._span)
        self._trace.current_span = self._span
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._span.end_ms = time.time() * 1000
        if exc_type:
            self._span.error = f"{exc_type.__name__}: {exc_val}"
            self._trace.current_span.error = self._span.error
        self._trace.current_span = self._prev_span
        return False


# ─── 核心API ─────────────────────────────────────────────────────────────────

class TraceContext:
    """
    全链路追踪上下文管理器。
    
    用法：
        with TraceContext("pipeline.run") as ctx:
            ctx.put("input", text)
            result = check10d(text)
            ctx.put("verdict", result.verdict)
    
    或者直接用 trace_call（推荐）：
        result = trace_call("judgment.check10d", lambda: check10d(text))
    """
    
    def __init__(self, root_name: str):
        self._root_name = root_name
        self._trace: Optional[TraceData] = None
    
    def __enter__(self) -> TraceData:
        trace_id = os.environ.get("JUHUO_TRACE_ID") or _gen_trace_id()
        root = Span(span_id=_short_id(), name=self._root_name, start_ms=time.time() * 1000)
        self._trace = TraceData(trace_id=trace_id, root_span=root, current_span=root)
        self._token = _current_trace.set(self._trace)
        _trace_enabled.set(True)
        return self._trace
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trace is None:
            return False
        self._trace.root_span.end_ms = time.time() * 1000
        if exc_type:
            self._trace.root_span.error = f"{exc_type.__name__}: {exc_val}"
        _write_trace(self._trace)
        try:
            _current_trace.reset(self._token)
        except Exception:
            pass
        _trace_enabled.set(False)
        return False


def end_trace(trace: TraceData) -> None:
    """手动结束 trace 并写入 causal_memory（一般不需要手动调用）"""
    trace.root_span.end_ms = time.time() * 1000
    _write_trace(trace)
    try:
        _current_trace.reset(trace._token)
    except Exception:
        pass
    _trace_enabled.set(False)

    _trace_enabled.set(False)
    # 写入 causal_memory（异步，不阻塞）
    _write_trace(trace)


def get_current_trace() -> Optional[TraceData]:
    """获取当前 trace（协程内可用）"""
    return _current_trace.get()


def get_current_trace_id() -> Optional[str]:
    """获取当前 trace_id"""
    t = _current_trace.get()
    return t.trace_id if t else None


def trace_call(name: str, func: Callable[[], Any], **fields) -> Any:
    """
    自动追踪函数调用（推荐用法）。
    
    用法：
        result = trace_call("judgment.check10d", lambda: check10d(text))
    
    等价于：
        with TraceContext(name) as ctx:
            ctx.put("...", ...)
            return func()
    """
    if not is_tracing_enabled():
        # 外部没有 trace，创建新的
        with TraceContext(name) as ctx:
            for k, v in fields.items():
                ctx.put(k, v)
            try:
                return func()
            except Exception as e:
                ctx.set_error(f"{type(e).__name__}: {e}")
                raise
        # end_trace 在 with 退出时自动调用
    else:
        # 已有 trace，在当前 span 下创建子 span
        trace = _current_trace.get()
        with trace.span(name) as span:
            for k, v in fields.items():
                span.fields[k] = _serialize(v)
            try:
                return func()
            except Exception as e:
                span.error = f"{type(e).__name__}: {e}"
                raise


def trace_span(name: str, **fields):
    """
    装饰器：自动追踪被装饰函数。
    
    用法：
        @trace_span("judgment.check10d")
        def my_check(text):
            return check10d(text)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return trace_call(
                name,
                lambda: func(*args, **kwargs),
                **fields
            )
        return wrapper
    return decorator


# ─── 因果记忆集成 ─────────────────────────────────────────────────────────────

def _write_trace(trace: TraceData) -> None:
    """将 trace 写入 causal_memory/traces/（同步写入）"""
    try:
        trace_dir = os.path.join(os.path.dirname(__file__), "causal_memory", "traces")
        os.makedirs(trace_dir, exist_ok=True)
        trace_file = os.path.join(trace_dir, f"{trace.root_span.name}.jsonl")
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        pass  # 禁止追踪时不阻塞主流程


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def _gen_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _serialize(value: Any) -> Any:
    """将值序列化为 JSON 兼容格式"""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    # dataclass / object
    if hasattr(value, "__dataclass_fields__"):
        return {f: _serialize(getattr(value, f)) for f in value.__dataclass_fields__}
    if hasattr(value, "__dict__"):
        return {k: _serialize(v) for k, v in value.__dict__.items() if not k.startswith("_")}
    try:
        return str(value)
    except Exception:
        return repr(value)


# ─── CLI 查看 ────────────────────────────────────────────────────────────────

def print_trace(trace: TraceData, indent: int = 0) -> None:
    """打印 trace 结构（调试用）"""
    prefix = "  " * indent
    span = trace.root_span
    dur = span.duration_ms()
    err = f" ❌ {span.error}" if span.error else ""
    print(f"{prefix}▶ {span.name} [{span.span_id}] {dur:.1f}ms{err}")
    for child in span.children:
        _print_span(child, indent + 1)


def _print_span(span: Span, indent: int) -> None:
    prefix = "  " * indent
    dur = span.duration_ms()
    err = f" ❌ {span.error}" if span.error else ""
    fields_str = ""
    if span.fields:
        fields_str = " | " + " | ".join(f"{k}={_truncate(v)}" for k, v in list(span.fields.items())[:5])
    print(f"{prefix}├ {span.name} [{span.span_id}] {dur:.1f}ms{err}{fields_str}")
    for child in span.children:
        _print_span(child, indent + 1)


def _truncate(value: Any, maxlen: int = 50) -> str:
    s = str(value)
    return s[:maxlen] + "..." if len(s) > maxlen else s
