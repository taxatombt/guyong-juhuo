#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env_loader.py — 类型安全的配置加载

借鉴 QwenPaw/CoPaw constant.py 的 EnvVarLoader 设计
"""

from __future__ import annotations
import os
import platform
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class EnvVarLoader:
    """类型安全的配置加载器"""
    
    @staticmethod
    def get_bool(env_var: str, default: bool = False) -> bool:
        val = os.environ.get(env_var, str(default)).lower()
        return val in ("true", "1", "yes", "on")
    
    @staticmethod
    def get_float(env_var: str, default: float = 0.0, min_v: float = None, max_v: float = None) -> float:
        try:
            v = float(os.environ.get(env_var, str(default)))
            if min_v is not None: v = max(min_v, v)
            if max_v is not None: v = min(max_v, v)
            return v
        except: return default
    
    @staticmethod
    def get_int(env_var: str, default: int = 0, min_v: int = None, max_v: int = None) -> int:
        try:
            v = int(os.environ.get(env_var, str(default)))
            if min_v is not None: v = max(min_v, v)
            if max_v is not None: v = min(max_v, v)
            return v
        except: return default
    
    @staticmethod
    def get_str(env_var: str, default: str = "") -> str:
        return os.environ.get(env_var, default)


# 路径配置
USER_HOME = Path(os.path.expanduser("~"))
JUHuo_USER_DIR = USER_HOME / ".juhuo"
JUHuo_USER_ENV = JUHuo_USER_DIR / ".env"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PROJECT_ENV = PROJECT_ROOT / ".env.example"


def load_env_files() -> list[Path]:
    """加载 .env 文件"""
    loaded = []
    for path in [JUHuo_USER_ENV, PROJECT_ENV]:
        if path.exists():
            load_dotenv(path, override=(path == JUHuo_USER_ENV))
            loaded.append(path)
    return loaded


def ensure_user_dir() -> Path:
    JUHuo_USER_DIR.mkdir(parents=True, exist_ok=True)
    return JUHuo_USER_DIR


def create_env_template() -> Path:
    """创建 .env 模板文件到用户目录"""
    ensure_user_dir()
    template = """# Juhuo 环境变量配置
# MiniMax API
MINIMAX_API_KEY=your_minimax_api_key_here
MINIMAX_MODEL=abab6.5s-chat

# OpenAI (可选)
OPENAI_API_KEY=your_openai_api_key_here

# Ollama (可选)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# 日志
LOG_LEVEL=INFO
"""
    path = JUHuo_USER_DIR / ".env.example"
    if not path.exists():
        path.write_text(template, encoding="utf-8")
    return path


# 自动加载
load_env_files()


if __name__ == "__main__":
    print(f"User dir: {JUHuo_USER_DIR}")
    print(f"LLM_MAX_CONCURRENT: {EnvVarLoader.get_int('LLM_MAX_CONCURRENT', 10)}")
