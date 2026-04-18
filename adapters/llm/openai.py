#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI 大模型适配器
"""

import os
from typing import Optional
import openai

from .base import LLMAdapter, LLMResponse, CompletionRequest


class OpenAIAdapter(LLMAdapter):
    """
    OpenAI 大模型适配
    支持 GPT-3.5 / GPT-4o 等模型
    """
    
    DEFAULT_API_BASE = "https://api.openai.com/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
        api_base: str = DEFAULT_API_BASE,
    ):
        super().__init__()  # 必须调用父类
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model_name
        self.api_base = api_base
        
        # 配置 openai
        openai.api_key = self.api_key
        openai.api_base = self.api_base
    
    def is_configured(self) -> bool:
        """检查是否配置正确"""
        return bool(self.api_key)
    
    def _complete_impl(self, request: CompletionRequest) -> LLMResponse:
        """调用 OpenAI 补全"""
        if not self.is_configured():
            return LLMResponse(
                success=False,
                content="",
                error="OPENAI_API_KEY not configured",
            )
        
        try:
            messages = [
                {"role": "user", "content": request.prompt},
            ]
            
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop,
                stream=False,
            )
            
            content = response.choices[0].message.content or ""
            usage = response.usage
            
            return LLMResponse(
                success=True,
                content=content,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            
        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                error=str(e),
            )
