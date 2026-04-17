#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rate_limiter.py — LLM 请求限流 + Retry 系统

借鉴 QwenPaw/CoPaw constant.py 设计：
- LLM_MAX_CONCURRENT: 最大并发
- LLM_MAX_QPM: 每分钟请求数
- LLM_BACKOFF_BASE/CAP: 指数退避
- LLM_RATE_LIMIT_PAUSE: 429 暂停时间
- LLM_MAX_RETRIES: 最大重试次数
"""

from __future__ import annotations
import asyncio
import time
import random
import logging
from typing import Callable, Any, Optional, TypeVar
from dataclasses import dataclass, field
from functools import wraps

from judgment.logging_config import get_logger
log = get_logger("juhuo.rate_limiter")


# ── 配置常量 ─────────────────────────────────────────────────────────────────

LLM_MAX_CONCURRENT: int = 10      # 最大并发 LLM 调用
LLM_MAX_QPM: int = 600            # 每分钟请求数（0=无限）
LLM_BACKOFF_BASE: float = 1.0     # 退避基数（秒）
LLM_BACKOFF_CAP: float = 10.0     # 退避上限（秒）
LLM_RATE_LIMIT_PAUSE: float = 5.0 # 429 暂停基础时间
LLM_RATE_LIMIT_JITTER: float = 1.0 # 随机抖动
LLM_MAX_RETRIES: int = 3          # 最大重试次数
LLM_ACQUIRE_TIMEOUT: float = 300.0 # 获取信号量超时

T = TypeVar("T")


# ── 滑动窗口限流 ─────────────────────────────────────────────────────────────

class SlidingWindowRateLimiter:
    """
    滑动窗口限流器
    
    基于时间窗口的 QPM 控制，防止 429
    """
    
    def __init__(self, max_qpm: int = 0):
        self.max_qpm = max_qpm
        self.window_seconds = 60.0
        self.requests: list[float] = []
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None
    
    def _clean_old(self, now: float) -> None:
        """清理过期请求"""
        cutoff = now - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
    
    def can_proceed(self) -> bool:
        """检查是否可以继续"""
        if self.max_qpm <= 0:
            return True
        
        now = time.time()
        self._clean_old(now)
        return len(self.requests) < self.max_qpm
    
    async def acquire(self, timeout: float = LLM_ACQUIRE_TIMEOUT) -> bool:
        """
        获取许可（异步）
        
        超过 timeout 返回 False
        """
        start = time.time()
        
        while True:
            if self.can_proceed():
                self.requests.append(time.time())
                return True
            
            if time.time() - start >= timeout:
                log.warning(f"Rate limiter timeout after {timeout}s")
                return False
            
            # 等待后重试
            wait_time = 0.1 + random.uniform(0, 0.1)
            await asyncio.sleep(wait_time)
    
    def sync_acquire(self, timeout: float = LLM_ACQUIRE_TIMEOUT) -> bool:
        """同步版本"""
        start = time.time()
        
        while True:
            if self.can_proceed():
                self.requests.append(time.time())
                return True
            
            if time.time() - start >= timeout:
                return False
            
            time.sleep(0.1)


# ── 并发控制 ─────────────────────────────────────────────────────────────────

class ConcurrencyLimiter:
    """
    并发数限制器
    
    基于信号量的最大并发控制
    """
    
    def __init__(self, max_concurrent: int = LLM_MAX_CONCURRENT):
        self.max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()
        self._current = 0
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
    async def acquire(self, timeout: float = LLM_ACQUIRE_TIMEOUT) -> bool:
        """获取许可"""
        try:
            await asyncio.wait_for(
                self._get_semaphore().acquire(),
                timeout=timeout
            )
            async with self._lock:
                self._current += 1
            return True
        except asyncio.TimeoutError:
            log.warning(f"Concurrency limit timeout after {timeout}s")
            return False
    
    def release(self) -> None:
        """释放许可"""
        self._semaphore.release() if self._semaphore else None
        self._current -= 1
    
    def current(self) -> int:
        return self._current


# ── Retry + Backoff ──────────────────────────────────────────────────────────

class RetryError(Exception):
    """重试耗尽"""
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = LLM_MAX_RETRIES
    backoff_base: float = LLM_BACKOFF_BASE
    backoff_cap: float = LLM_BACKOFF_CAP
    jitter: float = LLM_RATE_LIMIT_JITTER
    retry_on: tuple = ("rate_limit", "timeout", "connection")
    
    def calculate_delay(self, attempt: int) -> float:
        """计算退避延迟"""
        delay = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        delay += random.uniform(0, self.jitter)
        return delay


async def with_retry(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    带重试的异步调用
    
    Usage:
        result = await with_retry(llm.chat, messages, config=RetryConfig(max_retries=5))
    """
    cfg = config or RetryConfig()
    last_error: Optional[Exception] = None
    
    for attempt in range(cfg.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        
        except Exception as e:
            last_error = e
            error_type = type(e).__name__.lower()
            
            # 检查是否应该重试
            should_retry = any(r in error_type for r in cfg.retry_on)
            should_retry = should_retry or "429" in str(e)
            should_retry = should_retry or "timeout" in str(e).lower()
            should_retry = should_retry or "connection" in str(e).lower()
            
            if not should_retry or attempt >= cfg.max_retries:
                raise RetryError(attempt + 1, e) from e
            
            delay = cfg.calculate_delay(attempt)
            log.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
    
    raise RetryError(cfg.max_retries + 1, last_error or Exception("Unknown"))


def with_retry_sync(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """同步版本"""
    cfg = config or RetryConfig()
    last_error: Optional[Exception] = None
    
    for attempt in range(cfg.max_retries + 1):
        try:
            return func(*args, **kwargs)
        
        except Exception as e:
            last_error = e
            should_retry = attempt < cfg.max_retries
            
            if not should_retry:
                raise RetryError(attempt + 1, e) from e
            
            delay = cfg.calculate_delay(attempt)
            log.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
    
    raise RetryError(cfg.max_retries + 1, last_error or Exception("Unknown"))


# ── 全局限流器 ────────────────────────────────────────────────────────────────

_rate_limiter: Optional[SlidingWindowRateLimiter] = None
_concurrency_limiter: Optional[ConcurrencyLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter(max_qpm=LLM_MAX_QPM)
    return _rate_limiter


def get_concurrency_limiter() -> ConcurrencyLimiter:
    global _concurrency_limiter
    if _concurrency_limiter is None:
        _concurrency_limiter = ConcurrencyLimiter(max_concurrent=LLM_MAX_CONCURRENT)
    return _concurrency_limiter


# ── LLM 调用装饰器 ────────────────────────────────────────────────────────────

def llm_call(config: Optional[RetryConfig] = None):
    """
    LLM 调用装饰器
    
    自动限流 + 重试
    
    Usage:
        @llm_call()
        async def call_llm(messages):
            return await llm.chat(messages)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            rate_limiter = get_rate_limiter()
            concurrency = get_concurrency_limiter()
            
            # 限流获取
            if not await rate_limiter.acquire():
                raise RetryError(0, Exception("Rate limit acquisition failed"))
            
            if not await concurrency.acquire():
                concurrency.release()
                raise RetryError(0, Exception("Concurrency limit reached"))
            
            try:
                return await with_retry(func, *args, config=config, **kwargs)
            finally:
                concurrency.release()
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test
    print(f"Max Concurrent: {LLM_MAX_CONCURRENT}")
    print(f"Max QPM: {LLM_MAX_QPM}")
    print(f"Backoff: {LLM_BACKOFF_BASE}s - {LLM_BACKOFF_CAP}s")
    
    limiter = SlidingWindowRateLimiter(max_qpm=10)
    print(f"Can proceed: {limiter.can_proceed()}")
    
    cfg = RetryConfig(max_retries=3)
    print(f"Delay attempt 0: {cfg.calculate_delay(0):.2f}s")
    print(f"Delay attempt 1: {cfg.calculate_delay(1):.2f}s")
    print(f"Delay attempt 2: {cfg.calculate_delay(2):.2f}s")
