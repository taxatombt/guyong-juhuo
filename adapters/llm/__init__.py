#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_adapter — 聚活大模型接入适配器

支持多种大模型：
- MiniMax（用户当前使用）
- OpenAI
- Ollama（本地模型）
- 可扩展其他

用途：
- 文本补全
- 知识提取（从长文本提取可进化知识单元）
- 进化建议（基于现有技能建议改进）
"""

from .base import (
    LLMAdapter,
    LLMResponse,
    CompletionRequest,
)

from .minimax import MiniMaxAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter
from .config import load_config, get_adapter

__all__ = [
    # Types
    'LLMAdapter',
    'LLMResponse',
    'CompletionRequest',
    # Classes
    'MiniMaxAdapter',
    'OpenAIAdapter',
    'OllamaAdapter',
    # Functions
    'load_config',
    'get_adapter',
]
