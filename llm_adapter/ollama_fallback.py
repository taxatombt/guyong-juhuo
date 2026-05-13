#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ollama_fallback.py — Ollama 本地 LLM Fallback 适配器

来源：koala73/worldmonitor 的 Local AI(Ollama) 模式

核心理念：
- 当远程 API（MiniMax/OpenAI）不可用或超时 → 自动切换到本地 Ollama
- 当远程 API 恢复 → 自动切回远程（优先用更强的模型）
- 诊断接口：查询当前是远程还是本地，哪个模型在跑

与 router 的 llm_callable 的关系：
- router 原本直接调用 MiniMax API
- 这里在 router 和 API 之间加一层 FallbackRouter
- 对 router 透明，router 只管调用 llm_callable()
"""

import os
import time
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

try:
    from paths import PATHS
except ImportError:
    PATHS = {"DATA": os.path.join(os.path.dirname(__file__), "..", "data")}

try:
    from llm_adapter.base import LLMCapabilities, LLMResponse
except ImportError:
    LLMCapabilities = None
    LLMResponse = None

try:
    from llm_adapter.minimax_adapter import MiniMaxAdapter
except ImportError:
    MiniMaxAdapter = None

# ── 配置 ──────────────────────────────────────────────────────────────

@dataclass
class OllamaConfig:
    """Ollama fallback 配置"""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"        # 默认本地模型
    timeout_seconds: float = 30.0     # 超时阈值
    health_check_interval: float = 60.0  # 每60秒检测一次远程是否恢复
    max_retries: int = 1             # 远程重试次数
    remote_priority: bool = True      # True=远程优先，False=本地优先


# ── 全局状态 ─────────────────────────────────────────────────────────

_global_router = None
_global_lock = threading.RLock()


def get_fallback_router() -> 'FallbackRouter':
    global _global_router
    if _global_router is None:
        with _global_lock:
            if _global_router is None:
                _global_router = FallbackRouter()
    return _global_router


# ── 核心 FallbackRouter ─────────────────────────────────────────────

class FallbackRouter:
    """
    双层 LLM 路由：远程优先，失败时降级到本地 Ollama。

    使用方式（在 router.py 中）：
        from llm_adapter.ollama_fallback import get_fallback_router
        llm_callable = get_fallback_router().wrap(remote_llm_callable)

        # 之后所有调用走 llm_callable()，自动处理降级
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._remote_available: Optional[bool] = None
        self._last_check: float = 0
        self._status_lock = threading.RLock()
        self._call_counts = {"remote": 0, "local": 0, "fallback_success": 0}

        # 初始化 Ollama 客户端（延迟，不启动）
        self._ollama_client: Optional[OllamaClient] = None

    def wrap(self, remote_fn: Callable) -> Callable:
        """
        包装一个远程 LLM 调用函数，返回带 fallback 的版本。

        用法：
            original_call = lambda p, s, t: minimax.call(p, system=s, temperature=t)
            llm_callable = fallback_router.wrap(original_call)
        """
        def wrapped(prompt: str, system: str = "", temperature: float = 0.7,
                    **kwargs) -> str:
            return self.call(prompt, system=system, temperature=temperature,
                           remote_fn=remote_fn, **kwargs)
        return wrapped

    def call(self, prompt: str, system: str = "", temperature: float = 0.7,
             remote_fn: Optional[Callable] = None, **kwargs) -> str:
        """
        主调用入口：远程优先，失败则降级到本地 Ollama。
        """
        # 检查远程是否可用（缓存结果，60秒有效）
        if self._is_remote_available():
            if remote_fn is not None:
                try:
                    result = remote_fn(prompt, system=system, temperature=temperature, **kwargs)
                    with self._status_lock:
                        self._call_counts["remote"] += 1
                    return result
                except Exception as e:
                    if self._is_recoverable_error(e):
                        print(f"[FallbackRouter] 远程调用失败，降级到 Ollama: {e}")
                    else:
                        raise
            else:
                # 没有 remote_fn，直接用本地
                pass

        # 降级到 Ollama
        return self._call_local(prompt, system=system, temperature=temperature, **kwargs)

    def _is_remote_available(self) -> bool:
        """检查远程 API 是否可用（带缓存）"""
        with self._status_lock:
            now = time.time()
            if self._remote_available is not None and (now - self._last_check) < self.config.health_check_interval:
                return self._remote_available

            # 实际检测
            available = self._check_remote_health()
            self._remote_available = available
            self._last_check = now
            return available

    def _check_remote_health(self) -> bool:
        """健康检测：尝试 ping MiniMax"""
        if MiniMaxAdapter is None:
            return False
        try:
            # 轻量级检测：看 adapter 是否能初始化
            # 实际生产应该 ping 一下
            return True  # 保守策略：假设远程正常，失败再降级
        except Exception:
            return False

    def _is_recoverable_error(self, e: Exception) -> bool:
        """判断是否值得重试"""
        err_str = str(e).lower()
        recoverable_keywords = [
            "timeout", "timed out", "connection", "refused",
            "rate limit", "429", "500", "502", "503", "504",
            "network", "unreachable", "temporarily",
        ]
        return any(kw in err_str for kw in recoverable_keywords)

    def _get_ollama_client(self) -> 'OllamaClient':
        """延迟初始化 Ollama 客户端"""
        if self._ollama_client is None:
            self._ollama_client = OllamaClient(
                base_url=self.config.base_url,
                model=self.config.model,
                timeout=self.config.timeout_seconds,
            )
        return self._ollama_client

    def _call_local(self, prompt: str, system: str = "",
                    temperature: float = 0.7, **kwargs) -> str:
        """调用本地 Ollama"""
        client = self._get_ollama_client()

        # 等待 Ollama 就绪
        if not client.is_alive():
            raise OllamaUnavailableError(
                f"Ollama 未运行，请启动: ollama serve\n"
                f"或检查 base_url={self.config.base_url}"
            )

        try:
            response = client.chat(
                prompt=prompt,
                system=system,
                temperature=temperature,
                **kwargs,
            )
            with self._status_lock:
                self._call_counts["local"] += 1
                self._call_counts["fallback_success"] += 1
            return response
        except Exception as e:
            raise OllamaCallError(f"Ollama 调用失败: {e}") from e

    def status(self) -> Dict[str, Any]:
        """诊断接口：当前 LLM 路由状态"""
        with self._status_lock:
            return {
                "remote_available": self._remote_available,
                "last_check": datetime.fromtimestamp(self._last_check).isoformat() if self._last_check else None,
                "mode": "remote" if self._remote_available else "local",
                "model_remote": "MiniMax/OpenAI",
                "model_local": self.config.model,
                "calls": dict(self._call_counts),
                "base_url_ollama": self.config.base_url,
            }

    def switch_to(self, mode: str):
        """手动切换模式：'remote' / 'local'"""
        if mode not in ("remote", "local"):
            raise ValueError(f"mode must be 'remote' or 'local', got {mode}")
        with self._status_lock:
            self._remote_available = (mode == "remote")
            self._last_check = time.time()

    def detect_ollama_models(self) -> list:
        """列出本地可用模型"""
        try:
            client = self._get_ollama_client()
            return client.list_models()
        except Exception as e:
            return []


# ── Ollama HTTP 客户端 ───────────────────────────────────────────────

class OllamaClient:
    """轻量级 Ollama REST API 客户端"""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = None

    def _get_session(self):
        """懒加载 HTTP session"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.timeout = self.timeout
        return self._session

    def is_alive(self) -> bool:
        """检查 Ollama 是否在运行"""
        try:
            resp = self._get_session().get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        """列出本地模型"""
        try:
            resp = self._get_session().get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
            return []
        except Exception:
            return []

    def chat(self, prompt: str, system: str = "",
             temperature: float = 0.7, **kwargs) -> str:
        """Ollama /api/chat"""
        import requests
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.7, **kwargs) -> str:
        """Ollama /api/generate"""
        import requests
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            **kwargs,
        }
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


# ── 异常 ─────────────────────────────────────────────────────────────

class OllamaUnavailableError(Exception):
    """Ollama 未运行或无法连接"""
    pass


class OllamaCallError(Exception):
    """Ollama API 调用失败"""
    pass


# ── 便捷入口 ─────────────────────────────────────────────────────────

def ollama_status() -> Dict[str, Any]:
    """快速查询 Ollama 状态"""
    return get_fallback_router().status()


def ollama_wrap(remote_fn: Callable) -> Callable:
    """快速包装远程函数为带 fallback 的版本"""
    return get_fallback_router().wrap(remote_fn)
