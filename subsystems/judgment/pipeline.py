#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — Judgment Pipeline 入口

check10d_full: 完整流水线（router 10维 + 置信度 + Adversarial + Embedding）
"""

from typing import Dict, Optional
from judgment.router import check10d, check10d_run


def check10d_full(task_text: str, agent_profile: Optional[Dict] = None, complexity: str = "auto") -> Dict:
    """
    完整判断流水线

    调用 router 的 check10d_run() 获取完整结果。
    benchmark 用这个来跑所有案例。
    """
    try:
        result = check10d_run(task_text, agent_profile)
        if result is None:
            # fallback：直接用 check10d
            result = check10d(task_text, agent_profile, complexity)
        return result
    except Exception as e:
        # graceful degradation
        return {
            "task": task_text,
            "verdict": f"[Error: {e}]",
            "confidence": 0.0,
            "dimensions": [],
            "complexity": complexity,
        }
