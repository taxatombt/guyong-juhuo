# ─────────────────────────────────────────────────────────────────────────────
# circuit_breaker.py — 断路器（TencentDB-Agent-Memory 启发）
#
# 来源：Tencent/TencentDB-Agent-Memory 的 GatewaySupervisor 断路器设计
# 文档：workspace_tools/tencentdb-agent-memory/SKILL.md
#
# 作用：防止 LLM 调用级联失败。
#       当某个 LLM adapter（MiniMax/Ollama）连续失败 N 次后，熔断 60 秒，
#       期间所有请求直接返回降级结果，避免把系统拖死。
#
# 用法：
#   from utils.circuit_breaker import circuit_breaker, CircuitBreakerState
#
#   @circuit_breaker("minimax")
#   def call_minimax(msg):
#       return minimax.call(msg)
#
#   # 或手动控制
#   breaker = CircuitBreaker("ollama", threshold=3, cooldown=30)
#   if not breaker.is_open():
#       try:
#           result = ollama.call(msg)
#           breaker.record_success()
#       except Exception as e:
#           breaker.record_failure()
#           raise
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import threading
import time
import logging
from enum import Enum
from typing import Callable, Optional, TypeVar, ParamSpec
from functools import wraps

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CircuitBreakerState(Enum):
    CLOSED   = "closed"    # 正常，请求通过
    OPEN     = "open"      # 熔断，拒绝所有请求
    HALF_OPEN = "half_open"  # 试探，允许一个请求通过


class CircuitBreaker:
    """
    断路器实现。

    状态机：
        CLOSED ──(failure≥threshold)──→ OPEN
        OPEN ──(cooldown到期)──────────→ HALF_OPEN
        HALF_OPEN ──(成功)────────────→ CLOSED
        HALF_OPEN ──(失败)────────────→ OPEN（重新计时）
    """

    def __init__(
        self,
        name: str,
        threshold: int = 5,
        cooldown_seconds: float = 60.0,
        half_open_successes_needed: int = 1,
    ):
        self.name = name
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_successes_needed = half_open_successes_needed

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    # ── 公共 API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            self._maybe_transition()
            return self._state

    def is_closed(self) -> bool:
        return self.state == CircuitBreakerState.CLOSED

    def is_open(self) -> bool:
        return self.state == CircuitBreakerState.OPEN

    def is_half_open(self) -> bool:
        return self.state == CircuitBreakerState.HALF_OPEN

    def record_success(self) -> None:
        """记录一次成功调用。"""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_successes_needed:
                    self._transition_to(CircuitBreakerState.CLOSED)
                    logger.info(f"[CircuitBreaker:{self.name}] ⟳ CLOSED (recovery)")
            elif self._state == CircuitBreakerState.CLOSED:
                # 成功后重置失败计数
                self._failure_count = 0

    def record_failure(self) -> None:
        """记录一次失败调用。超过阈值则断开。"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitBreakerState.CLOSED:
                if self._failure_count >= self.threshold:
                    self._transition_to(CircuitBreakerState.OPEN)
                    logger.warning(
                        f"[CircuitBreaker:{self.name}] ⚡ OPEN after {self._failure_count} failures"
                    )
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # 试探失败，立即重新熔断
                self._transition_to(CircuitBreakerState.OPEN)
                self._half_open_successes = 0

    def allow_request(self) -> bool:
        """判断是否允许请求通过。"""
        state = self.state
        if state == CircuitBreakerState.CLOSED:
            return True
        if state == CircuitBreakerState.HALF_OPEN:
            return True
        return False  # OPEN

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _maybe_transition(self) -> None:
        """检查是否需要从 OPEN → HALF_OPEN。"""
        if self._state != CircuitBreakerState.OPEN:
            return
        if self._last_failure_time is None:
            return
        elapsed = time.time() - self._last_failure_time
        if elapsed >= self.cooldown_seconds:
            self._transition_to(CircuitBreakerState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        old = self._state
        self._state = new_state
        if new_state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            self._half_open_successes = 0
        elif new_state == CircuitBreakerState.OPEN:
            pass  # _last_failure_time 已在上层 set
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self._half_open_successes = 0
        logger.debug(f"[CircuitBreaker:{self.name}] {old.value} → {new_state.value}")


# ── 全局断路器注册表 ────────────────────────────────────────────────────────

_circuit_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    """获取或创建命名断路器。"""
    with _breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, **kwargs)
        return _circuit_breakers[name]


def circuit_breaker(name: str, threshold: int = 5, cooldown: float = 60.0):
    """
    装饰器：为函数加断路器保护。

    用法：
        @circuit_breaker("minimax", threshold=3, cooldown=30)
        def call_minimax(msg):
            return minimax.post(msg)

    断路器打开时，直接抛出 CircuitBreakerOpen 异常，调用方需处理。
    """
    breaker = get_breaker(name, threshold=threshold, cooldown_seconds=cooldown)

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not breaker.allow_request():
                raise CircuitBreakerOpen(
                    f"[CircuitBreaker:{name}] is OPEN — request rejected"
                )
            try:
                result = fn(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper

    return decorator


class CircuitBreakerOpen(Exception):
    """断路器打开时的异常。"""
    pass