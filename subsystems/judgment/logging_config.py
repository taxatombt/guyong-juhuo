#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logging_config.py — Juhuo 日志系统

标准方案：Python logging + 日志文件
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


# 日志目录
LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_FILE = LOG_DIR / "juhuo.log"
ERROR_FILE = LOG_DIR / "errors.log"

# 日志配置
LOG_LEVEL = logging.INFO
MAX_BYTES = 5 * 1024 * 1024   # 5MB
BACKUP_COUNT = 3


def setup_logging(name: str = None) -> logging.Logger:
    """
    获取 logger 实例
    
    Args:
        name: logger 名称，默认使用根 logger
        
    Returns:
        Logger 实例
    """
    logger = logging.getLogger(name or "juhuo")
    
    if logger.handlers:
        return logger  # 避免重复添加 handler
    
    logger.setLevel(LOG_LEVEL)
    
    # 日志格式
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 1. 控制台 Handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)  # 控制台只显示 WARNING+
    console.setFormatter(fmt)
    logger.addHandler(console)
    
    # 2. 普通日志文件
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录 DEBUG+
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    
    # 3. 错误日志文件（只记录 ERROR+）
    error_handler = RotatingFileHandler(
        ERROR_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    logger.addHandler(error_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """获取 logger（别名）"""
    return setup_logging(name)


# 常用 logger 快捷函数
def info(msg: str, name: str = None):
    get_logger(name).info(msg)

def warning(msg: str, name: str = None):
    get_logger(name).warning(msg)

def error(msg: str, name: str = None):
    get_logger(name).error(msg)

def debug(msg: str, name: str = None):
    get_logger(name).debug(msg)
