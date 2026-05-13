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


def format_dashboard(result: dict) -> str:
    """
    Dashboard 四维结构报告（迁移自 daily_stock_analysis 的 AI 决策仪表盘设计）。

    将 10 维度判断结果重组为 4 个结构化 section：
    - core_conclusion: 一句话结论 + 信号类型 + 仓位建议
    - data_perspective: 趋势状态 + 维度评分 + 量能分析
    - intelligence: 情绪标签 + 风险提示 + 催化剂
    - battle_plan: 置信度 + 行动建议 + 风险控制

    来源灵感：ZhuLinsen/daily_stock_analysis（35.8k★）
    """
    lines = []
    verdict = result.get("verdict", "（无结论）")
    confidence = result.get("confidence", 0.0)
    dimensions = result.get("dimensions", [])
    chain_id = result.get("chain_id", "")
    complexity = result.get("complexity", "")
    emotion_label = result.get("emotion_label", "")
    emotion_intensity = result.get("emotion_intensity", 0.0)
    warnings = result.get("warnings", [])
    reasoning_summary = result.get("reasoning_summary", "")

    # ── 信号类型判断 ──────────────────────────────────────────────
    if confidence >= 0.80:
        signal_type = "🟢 高置信"
    elif confidence >= 0.65:
        signal_type = "🟡 中置信"
    elif confidence >= 0.50:
        signal_type = "🟠 低置信"
    else:
        signal_type = "🔴 存疑"

    # ── 仓位建议（根据复杂度）────────────────────────────────────
    if complexity in ("critical", "complex"):
        position = "建议暂缓，需更多信息"
    elif confidence >= 0.75:
        position = "可执行，仓位≤20%"
    elif confidence >= 0.55:
        position = "谨慎执行，仓位≤10%"
    else:
        position = "不建议执行"

    # ── 维度分类映射 ─────────────────────────────────────────────
    data_dims = [d for d in dimensions if d.get("id") in (
        "cognitive", "game_theory", "economic", "dialectical", "temporal"
    )]
    intel_dims = [d for d in dimensions if d.get("id") in (
        "emotional", "intuitive", "moral", "social"
    )]
    meta_dim = next((d for d in dimensions if d.get("id") == "metacognitive"), None)

    # ── Section 1: core_conclusion ───────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  核心结论")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  {verdict}")
    lines.append(f"  信号：{signal_type} | 置信度：{confidence:.0%} | 复杂度：{complexity or '未知'}")
    lines.append(f"  建议：{position}")
    if emotion_label:
        lines.append(f"  情绪：{emotion_label}（强度 {emotion_intensity:.0%}）")
    lines.append("")

    # ── Section 2: data_perspective ──────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  数据视角")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if data_dims:
        # 找最高/最低维度
        sorted_dims = sorted(data_dims, key=lambda d: d.get("score", 0), reverse=True)
        for dim in sorted_dims:
            name = _dim_cn_name(dim.get("id", "?"))
            score = dim.get("score", 0)
            reasoning = dim.get("reasoning", "")[:60]
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            lines.append(f"  {name}  [{bar}] {score:.0%}")
            if reasoning:
                lines.append(f"    → {reasoning}")
    else:
        lines.append("  （无维度数据）")
    lines.append("")

    # ── Section 3: intelligence ──────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  智能洞察")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if intel_dims:
        for dim in intel_dims:
            name = _dim_cn_name(dim.get("id", "?"))
            score = dim.get("score", 0)
            reasoning = dim.get("reasoning", "")[:60]
            lines.append(f"  {name}（{score:.0%}）：{reasoning}")

    # 元认知维度作为自我提示
    if meta_dim:
        meta_score = meta_dim.get("score", 0)
        meta_reasoning = meta_dim.get("reasoning", "")[:60]
        lines.append(f"  元认知（{meta_score:.0%}）：{meta_reasoning}")

    # 风险警告
    if warnings:
        lines.append("  ⚠️ 风险提示：")
        for w in warnings[:3]:
            lines.append(f"    · {w}")

    # 推理摘要
    if reasoning_summary:
        lines.append(f"  💡 推理摘要：{reasoning_summary[:100]}")
    lines.append("")

    # ── Section 4: battle_plan ─────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  行动计划")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  置信度：{confidence:.0%}")
    lines.append(f"  行动：{verdict}")

    # 基于维度的行动建议
    if data_dims:
        strong_dim = max(data_dims, key=lambda d: d.get("score", 0))
        lines.append(f"  主要支撑：{_dim_cn_name(strong_dim.get('id','?'))}（{strong_dim.get('score',0):.0%}）")
    if intel_dims:
        weak_dim = min(intel_dims, key=lambda d: d.get("score", 0))
        lines.append(f"  需注意：{_dim_cn_name(weak_dim.get('id','?'))}（{weak_dim.get('score',0):.0%}）")

    lines.append(f"  风险控制：置信度{confidence:.0%}→仓位上限{'20%' if confidence>=0.75 else '10%' if confidence>=0.55 else '不建议'}")

    if chain_id:
        lines.append(f"  链ID：{chain_id}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def _dim_cn_name(dim_id: str) -> str:
    """维度 ID → 中文名称映射"""
    MAP = {
        "cognitive": "认知",
        "game_theory": "博弈",
        "economic": "经济",
        "dialectical": "辩证",
        "emotional": "情绪",
        "intuitive": "直觉",
        "moral": "道德",
        "social": "社会",
        "temporal": "时间",
        "metacognitive": "元认知",
    }
    return MAP.get(dim_id, dim_id)


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
