#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
__main__.py — Juhuo 入口

Usage:
    python -m juhuo [task]      # 判断
    python -m juhuo shell       # 交互
    python -m juhuo web         # Web Console
    python -m juhuo status      # 状态
    python -m juhuo verdict     # Verdict
    python -m juhuo config      # 配置
"""

from cli import main

if __name__ == "__main__":
    main()
