#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_adapter config — 配置加载，优先读取用户网页保存的配置文件
"""

import os
import json
from typing import Optional

from .base import LLMAdapter
from .minimax import MiniMaxAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter


def load_config() -> dict:
    """
    加载配置：
    1. 优先从 user_config.json 读取（网页端保存的配置）
    2.  fallback 到环境变量
    3.  fallback 到默认值
    """
    # 默认值
    default_config = {
        "provider": "minimax",
        "minimax_api_key": "",
        "minimax_group_id": "",
        "minimax_model": "mini-max-latest",
        "openai_api_key": "",
        "openai_model": "gpt-4o",
        "openai_api_base": "https://api.openai.com/v1",
        "ollama_model": "llama3:8b",
        "ollama_api_base": "http://localhost:11434",
    }
    
    # 尝试读取用户配置文件（网页端保存）
    config_path = os.path.join(os.path.dirname(__file__), "user_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            # 合并用户配置到默认
            default_config.update(user_config)
        except Exception:
            pass
    
    # 环境变量覆盖
    env_mapping = {
        "JUHUO_LLM_PROVIDER": "provider",
        "MINIMAX_API_KEY": "minimax_api_key",
        "MINIMAX_GROUP_ID": "minimax_group_id",
        "MINIMAX_MODEL": "minimax_model",
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_MODEL": "openai_model",
        "OPENAI_API_BASE": "openai_api_base",
        "OLLAMA_MODEL": "ollama_model",
        "OLLAMA_API_BASE": "ollama_api_base",
    }
    
    for env_name, config_key in env_mapping.items():
        val = os.getenv(env_name)
        if val is not None and val != "":
            default_config[config_key] = val
    
    return default_config


def get_adapter() -> Optional[LLMAdapter]:
    """
    根据配置获取适配器
    返回 None 表示没有配置好
    """
    config = load_config()
    provider = config["provider"]
    
    if provider == "minimax":
        adapter = MiniMaxAdapter(
            api_key=config["minimax_api_key"],
            model_name=config["minimax_model"],
        )
        if adapter.is_configured():
            return adapter
    
    elif provider == "openai":
        adapter = OpenAIAdapter(
            api_key=config["openai_api_key"],
            model_name=config["openai_model"],
            api_base=config["openai_api_base"],
        )
        if adapter.is_configured():
            return adapter
    
    elif provider == "ollama":
        adapter = OllamaAdapter(
            model_name=config["ollama_model"],
            api_base=config["ollama_api_base"],
        )
        if adapter.is_configured():
            return adapter
    
    return None
