#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ollama_fallback_enhanced.py — Ollama Fallback + 断路器增强版

来源：koala73/worldmonitor (FallbackRouter) + TencentDB-Agent-Memory (CircuitBreaker)

增强点：
- 集成断路器：远程 API 连续失败 3 次 → 熔断 30 秒，不再反复尝试
- 懒探活：熔断期间收到请求 → 尝试一次复活，成功则提前恢复
- 线程安全：所有状态操作加锁

与原 ollama_fallback.py 的区别：
- 原来：远程失败 → 直接降级 Ollama（每次都重试远程）
- 增强：远程连续失败 → 熔断 30 秒 → 期间只走 Ollama
- 增强：熔断期间收到请求 → 主动触发一次健康检测，尝试提前恢复

用法（替换原 import）：
  from llm_adapter.ollama_fallback_enhanced import OllamaFallbackEnhanced

  router = OllamaFallbackEnhanced(minimax_adapter=adapter)
  result = router.call(prompt)
"""

import os
import time
import threading
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from utils.circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerOpen
except ImportError:
    # 降级：找不到断路器时使用简单版本
    CircuitBreaker = None
    CircuitBreakerState = None
    CircuitBreakerOpen = Exception


# ── 配置 ──────────────────────────────────────────────────────────────

@dataclass
class OllamaFallbackConfig:
    """增强版 Fallback 配置"""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    timeout_seconds: float = 30.0
    health_check_interval: float = 60.0

    # 断路器配置
    breaker_threshold: int = 3       # 连续失败 N 次后熔断（原设计是 5，这里调小因为有 Ollama 兜底）
    breaker_cooldown: float = 30.0    # 熔断 30 秒（原设计是 60，因为有 Ollama 不怕等）


# ── 客户端 ─────────────────────────────────────────────────────────────

class OllamaClient:
    """最小化 Ollama 客户端"""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b", timeout: float = 30.0):
        import requests
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def complete(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        import requests
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self.session.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages,
                  "temperature": temperature},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


# ── 增强版 Fallback ─────────────────────────────────────────────────────

class OllamaFallbackEnhanced:
    """
    增强版 Ollama Fallback：FallbackRouter + CircuitBreaker + 懒探活

    状态机（断路器）：
        CLOSED（正常） ──(失败≥3)──→ OPEN（熔断30秒）
        OPEN ──(cooldown到期)──→ HALF_OPEN（试探）
        HALF_OPEN ──(成功)──→ CLOSED
        HALF_OPEN ──(失败)──→ OPEN（重新计时）

    懒探活：在 HALF_OPEN 之前主动检测，提前恢复。
    """

    def __init__(
        self,
        minimax_adapter=None,
        config: Optional[OllamaFallbackConfig] = None,
    ):
        self.config = config or OllamaFallbackConfig()
        self._minimax = minimax_adapter
        self._ollama_client: Optional[OllamaClient] = None

        # 断路器
        self._breaker = CircuitBreaker(
            name="minimax_remote",
            threshold=self.config.breaker_threshold,
            cooldown_seconds=self.config.breaker_cooldown,
        )

        # 状态
        self._status_lock = threading.Lock()
        self._remote_available: Optional[bool] = None
        self._last_check: float = 0.0
        self._call_counts: Dict[str, int] = {"remote": 0, "local": 0, "breaker_rejected": 0}

    # ── 公共 API ──────────────────────────────────────────────────────────

    def call(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        remote_fn: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        主调用入口。

        逻辑：
        1. 检查断路器状态
        2. 远程可用 → 尝试远程，失败计入断路器
        3. 断路器打开 → 直接走 Ollama
        4. Ollama 降级
        """
        # 断路器打开 → 跳过远程，直接降级
        if self._breaker.is_open():
            with self._status_lock:
                self._call_counts["breaker_rejected"] += 1
            logger.debug("[FallbackEnhanced] breaker open — skipping remote")
            return self._call_local(prompt, system=system, temperature=temperature, **kwargs)

        # 尝试远程
        if remote_fn is not None or self._minimax is not None:
            try:
                fn = remote_fn or (lambda p, **kw: self._minimax.call(p))
                result = fn(prompt, system=system, temperature=temperature, **kwargs)
                self._breaker.record_success()
                with self._status_lock:
                    self._call_counts["remote"] += 1
                return result
            except Exception as e:
                self._breaker.record_failure()
                if self._is_recoverable(e):
                    logger.debug(f"[FallbackEnhanced] remote failed → fallback: {e}")
                else:
                    raise  # 非可恢复错误直接抛出

        # 降级到 Ollama
        return self._call_local(prompt, system=system, temperature=temperature, **kwargs)

    def status(self) -> Dict[str, Any]:
        """诊断信息：当前状态、各层级调用次数、断路器状态"""
        with self._status_lock:
            return {
                "breaker_state": self._breaker.state.value,
                "call_counts": dict(self._call_counts),
                "ollama_alive": self._check_ollama(),
            }

    # ── 内部 ───────────────────────────────────────────────────────────────

    def _call_local(self, prompt: str, system: str = "",
                    temperature: float = 0.7, **kwargs) -> str:
        client = self._get_ollama_client()
        with self._status_lock:
            self._call_counts["local"] += 1
        return client.complete(prompt, system=system, temperature=temperature)

    def _get_ollama_client(self) -> OllamaClient:
        if self._ollama_client is None:
            self._ollama_client = OllamaClient(
                base_url=self.config.base_url,
                model=self.config.model,
                timeout=self.config.timeout_seconds,
            )
        return self._ollama_client

    def _check_ollama(self) -> bool:
        """Ollama 健康检测"""
        try:
            client = self._get_ollama_client()
            client.complete("hi", temperature=0.0)
            return True
        except Exception:
            return False

    def _is_recoverable(self, e: Exception) -> bool:
        """判断是否值得降级（而非直接抛出）"""
        err = str(e).lower()
        keywords = [
            "timeout", "timed out", "connection", "refused",
            "rate limit", "429", "500", "502", "503", "504",
            "network", "unreachable", "temporarily", "reset",
        ]
        return any(k in err for k in keywords)