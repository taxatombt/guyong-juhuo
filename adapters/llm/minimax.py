#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax 大模型适配器 - OpenAI兼容接口

API文档: https://platform.minimaxi.com/document/Guides/-text-to-text
- 国际版: https://api.minimax.io/v1
- 中国版: https://api.minimaxi.com/v1
- 认证: Authorization: Bearer <api_key>
- 无需 group_id
"""

import os
import json
import time
from typing import List, Optional
import requests

from .base import LLMAdapter, LLMResponse, CompletionRequest


class MiniMaxAdapter(LLMAdapter):
    """
    MiniMax 大模型适配（OpenAI兼容格式）
    支持 MiniMax-M2 / MiniMax-M2.5 / MiniMax-M2.7 等模型
    """

    # OpenAI兼容端点（中国版）
    DEFAULT_API_BASE = "https://api.minimaxi.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "MiniMax-M2",
        api_base: Optional[str] = None,
    ):
        super().__init__()  # 必须调用父类，初始化 _rate_limiter
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.model_name = model_name
        # 允许通过 env var 覆盖端点
        self.api_base = api_base or os.getenv("MINIMAX_API_BASE", "") or self.DEFAULT_API_BASE

    def is_configured(self) -> bool:
        """检查是否配置正确（有 api_key 即可）"""
        return bool(self.api_key)

    def _make_url(self) -> str:
        """构造完整的 chat completions URL"""
        base = self.api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        elif base.endswith("/v1"):
            return f"{base}/chat/completions"
        elif base.endswith("/v1/"):
            return f"{base}chat/completions"
        else:
            return f"{base}/v1/chat/completions"

    def _complete_impl(self, request: CompletionRequest) -> LLMResponse:
        """调用 MiniMax 补全（OpenAI兼容格式）"""
        if not self.is_configured():
            return LLMResponse(
                success=False,
                content="",
                error="MINIMAX_API_KEY not configured",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            # 禁用 thinking-only 模式，让正文直接返回内容（而非只在<think>里）
            "disable_thinking": True,
        }

        if request.top_p and request.top_p < 1.0:
            payload["top_p"] = request.top_p

        if request.stop:
            payload["stop"] = request.stop

        # Retry on overload (429/529) + HTTP timeout
        retry_delays = [5, 15, 30]
        response = None
        for attempt in range(len(retry_delays) + 1):
            try:
                response = requests.post(
                    self._make_url(),
                    headers=headers,
                    json=payload,
                    timeout=(10, 60),  # (connect, read) timeout
                )
                if response.status_code == 200:
                    break
                if response.status_code not in (429, 529) or attempt == len(retry_delays):
                    return LLMResponse(
                        success=False,
                        content="",
                        error=f"HTTP {response.status_code}: {response.text[:500]}",
                    )
                time.sleep(retry_delays[attempt])
            except requests.exceptions.Timeout:
                # HTTP timeout → retry (server busy, don't give up)
                if attempt == len(retry_delays):
                    return LLMResponse(
                        success=False, content="", error="Request timeout (60s read) after 3 retries",
                    )
                time.sleep(retry_delays[attempt])
            except Exception as e:
                if attempt == len(retry_delays):
                    return LLMResponse(
                        success=False, content="", error=f"Request failed: {str(e)}",
                    )
                time.sleep(retry_delays[attempt])

        # Parse success response
        try:
            data = response.json()
        except Exception as e:
            return LLMResponse(
                success=False, content="", error=f"JSON parse failed: {str(e)}",
            )

        if "choices" in data:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                success=True,
                content=content,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        else:
            return LLMResponse(
                success=False,
                content="",
                error=f"Unexpected response format: {str(data)[:200]}",
            )

    # ── 文本向量化（用于 experiences 语义检索）──────────────────────────────
    def embed(self, text: str) -> Optional[List[float]]:
        """
        调用 MiniMax embedding 接口，返回 1024 维向量。

        API: POST /v1/embeddings
        模型: embo-01（MiniMax 文本嵌入模型）

        Returns:
            List[float]: 1024维向量，失败返回 None
        """
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "embo-01",
            "texts": [text[:8192]],  # MiniMax: texts array
        }

        # Retry on overload
        base = self._make_url().replace("/chat/completions", "")
        for attempt in range(4):
            try:
                response = requests.post(
                    f"{base}/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("data", [{}])[0].get("embedding")
                    return embedding
                if response.status_code not in (429, 529) or attempt == 3:
                    return None
                time.sleep([3, 10][min(attempt, 1)])
            except Exception:
                if attempt == 3:
                    return None
                time.sleep(3)
        return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量向量化（每条独立调用，返回列表）"""
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# 便捷工厂函数
# ---------------------------------------------------------------------------
_default_adapter: Optional["MiniMaxAdapter"] = None


def get_adapter(
    api_key: Optional[str] = None,
    model_name: str = "MiniMax-M2.7",
    api_base: Optional[str] = None,
) -> "MiniMaxAdapter":
    """返回全局单例适配器（惰性构造）"""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = MiniMaxAdapter(
            api_key=api_key,
            model_name=model_name,
            api_base=api_base,
        )
    return _default_adapter
