"""
Hermes 集成模块工具函数
"""

from pathlib import Path
from typing import Optional
import os


def get_juhuo_root() -> Path:
    """Get聚活项目根目录
    
    尊重 JUHUO_ROOT 环境变量，否则自动推断
    """
    env_root = os.environ.get("JUHUO_ROOT")
    if env_root:
        return Path(env_root)
    
    # Try to find from this file's location
    # This file is at juhuo/hermes_integration/utils.py
    this_file = Path(__file__)
    return this_file.parent.parent


def get_data_dir() -> Path:
    """Get data directory"""
    root = get_juhuo_root()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
