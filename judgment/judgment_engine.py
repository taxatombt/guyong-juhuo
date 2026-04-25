# Shim: judgment/judgment_engine → judgment/router
# Migration: 2026-04-25
# MISSING file — creates runtime ImportError in tui.py:143 and multi_agent.py:223
# 真实实现: judgment/router.py 的 check10d() 函数（模块级顶层函数）
# multi_agent.py 和 tui.py 都只需 check10d，不需整个 JudgmentEngine 类
from judgment.router import check10d

__all__ = ["check10d"]
