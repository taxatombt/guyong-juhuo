#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
juhuo.py - DEPRECATED

此文件已废弃。请使用以下入口：

  python -m juhuo web           # Web Console（真实判断 pipeline，port 18768）
  python -m juhuo judge "问题"   # CLI 单次判断
  python -m juhuo shell         # 交互模式
  python -m juhuo mcp           # MCP Server（stdio）
"""
import sys, warnings
warnings.warn("juhuo.py is deprecated. Use 'python -m juhuo web' instead.", DeprecationWarning, stacklevel=2)

# 重定向到标准入口
from cli import main
sys.exit(main())