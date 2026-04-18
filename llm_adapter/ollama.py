#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama 本地大模型适配器
支持本地运行的开源模型，不需要联网
"""

import os
from typing import Optional
import requests

from .base import LLMAdapter, LLMResponse, CompletionRequest


class OllamaAdapter(LLMAdapter):
    """
    Ollama 本地大模型适配
    运行在本地，不需要API密钥
    默认地址 http://localhost:11434
    """
    
    DEFAULT_API_BASE = "http://localhost:11434"
    
    def __init__(
        self,
        model_name: str = "llama3:8b",
        api_base: str = DEFAULT_API_BASE,
    ):
        super().__init__()  # 必须调用父类
        self.model_name = model_name
        self.api_base = api_base.rstrip('/')
    
    def is_configured(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            response = requests.get(f"{self.api_base}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _complete_impl(self, request: CompletionRequest) -> LLMResponse:
        """调用 Ollama 补全"""
        if not self.is_configured():
            return LLMResponse(
                success=False,
                content="",
                error="Ollama service not available at {self.api_base}",
            )
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": request.prompt,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                    "top_p": request.top_p,
                }
            }
            
            if request.stop:
                payload["options"]["stop"] = request.stop
            
            response = requests.post(
                f"{self.api_base}/api/generate",
                json=payload,
                timeout=300,  # 本地模型可能慢，给更长超时
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    content="",
                    error=f"HTTP {response.status_code}: {response.text}",
                )
            
            data = response.json()
            content = data.get("response", "")
            
            # Ollama 提供 eval_count 大致对应 completion tokens
            # prompt_eval_count 对应 prompt tokens
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            
            return LLMResponse(
                success=True,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
            
        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                error=str(e),
            )
