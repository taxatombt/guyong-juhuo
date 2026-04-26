#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
router_utils.py — router.py 独立工具函数

从 router.py 提取的无依赖工具函数，供 pipeline 和 router 共享。
"""
import re
from typing import List


def _tok(s: str) -> int:
    """估算 token 数（简易版：中文3token/字，英文1token/词）"""
    import re
    s = s.strip()
    if not s:
        return 0
    en_words = len(re.findall(r'[a-zA-Z0-9]+', s))
    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', s))
    cn_punct = len(re.findall(r'[\u3000-\u303f\uff00-\uffef]', s))
    return en_words + zh_chars * 1.5 + cn_punct


def _keyword_match(text: str, keywords: List[str]) -> bool:
    """简单关键词匹配（供 _build_answer_prompt 使用）"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _judge_complexity(text: str) -> str:
    """
    任务复杂度判断（供 check10d 使用）。
    简单启发式：长度 + 关键词判断复杂度级别。
    """
    score = 0
    text_lower = text.lower()

    # 长度计分
    if len(text) > 200: score += 2
    elif len(text) > 80: score += 1

    # 复杂关键词
    complex_kw = ["是否", "要不要", "该不该", "选择", "决策",
                  "利弊", "优劣", "分析", "评估", "判断"]
    if any(kw in text for kw in complex_kw):
        score += 1

    # 极度复杂
    expert_kw = ["人生", "职业", "创业", "投资", "法律", "道德困境",
                 "价值观", "长期", "战略", "重大"]
    if sum(1 for kw in expert_kw if kw in text) >= 2:
        score += 2

    if score >= 3: return "critical"
    if score >= 2: return "complex"
    return "simple"


def format_report(result: dict) -> str:
    """
    文本报告格式化（供 check10d_run 使用）。
    把 check10d_run 的结果 dict 格式化为人类可读文本。
    """
    lines = []
    verdict = result.get("verdict", "（无结论）")
    confidence = result.get("confidence", 0.0)
    dimensions = result.get("dimensions", [])

    lines.append(f"## 十维判断结论")
    lines.append(f"** verdict: {verdict}")
    lines.append(f"** confidence: {confidence:.2f}")
    lines.append("")

    if dimensions:
        lines.append("### 各维度分析：")
        for dim in dimensions:
            name = dim.get("name", dim.get("id", "?"))
            score = dim.get("score", 0.0)
            reasoning = dim.get("reasoning", "")[:80]
            lines.append(f"- **{name}**({score:.2f}): {reasoning}")
        lines.append("")

    chain_id = result.get("chain_id", "")
    if chain_id:
        lines.append(f"_chain_id: {chain_id}_")

    return "\n".join(lines)


def format_structured(result: dict) -> str:
    """
    结构化格式化（供 check10d_run 使用）。
    把结果格式化为 JSON 友好的结构化文本。
    """
    import json
    parts = []
    verdict = result.get("verdict", "")
    confidence = result.get("confidence", 0.0)
    dimensions = result.get("dimensions", [])
    chain_id = result.get("chain_id", "")
    complexity = result.get("complexity", "auto")
    emotion_label = result.get("emotion_label", "")

    parts.append(f"VERDICT: {verdict}")
    parts.append(f"CONFIDENCE: {confidence:.3f}")
    parts.append(f"COMPLEXITY: {complexity}")

    if emotion_label:
        parts.append(f"EMOTION: {emotion_label}")

    if dimensions:
        dim_lines = []
        for dim in dimensions:
            name = dim.get("name", dim.get("id", "?"))
            score = dim.get("score", 0.0)
            dim_lines.append(f"{name}={score:.2f}")
        parts.append(f"DIMS: {' '.join(dim_lines)}")

    if chain_id:
        parts.append(f"CHAIN: {chain_id}")

    return " | ".join(parts)
