#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_orchestrator.py — LLM 编排层（从 router.py 提取）

职责：
- 快速响应函数（IntentRouter 旁路，无需 LLM）
- Profile → 维度个性化注入（biography/experiences 改变权重和追问方向）
- LLM 调用编排（同步包装）

被 router.py import 使用，保持 router.py 可测试性。
"""

from typing import Optional, Dict, List, Any


# ── 维度权重映射：profile 特征 → 维度权重调整 ──────────────────────────────
# agent_profile 中的 key/values/biases → 映射到具体维度的权重和追问方向

_DIMENSION_KEYWORDS: Dict[str, Dict[str, float]] = {
    # 长期主义 → temporal 最高权重
    "long_term": {
        "temporal": 1.8,
        "cognitive": 1.2,
        "game_theory": 1.1,
    },
    "5年": {"temporal": 1.8},
    "10年": {"temporal": 1.8},
    "长远": {"temporal": 1.8},
    "未来": {"temporal": 1.6},
    # 风险厌恶 → game_theory + economic 权重高
    "保守": {"game_theory": 1.5, "economic": 1.3, "emotional": 1.2},
    "谨慎": {"game_theory": 1.4, "economic": 1.2},
    "风险": {"game_theory": 1.6},
    # 情感驱动 → emotional + social 权重高
    "关系": {"emotional": 1.6, "social": 1.4},
    "家庭": {"emotional": 1.5, "social": 1.3},
    "感情": {"emotional": 1.7},
    # 理性分析 → cognitive + dialectical 权重高
    "理性": {"cognitive": 1.6, "dialectical": 1.4, "economic": 1.2},
    "分析": {"cognitive": 1.5},
    "逻辑": {"cognitive": 1.4},
    # 道德优先 → moral 权重高
    "道德": {"moral": 1.8, "social": 1.3},
    "原则": {"moral": 1.6},
    "良心": {"moral": 1.7},
    # 短期紧迫 → temporal(短期) + metacognitive 权重高
    "紧迫": {"temporal": 1.5, "metacognitive": 1.3},
    "马上": {"temporal": 1.4},
    "今天": {"temporal": 1.3},
    "现在": {"temporal": 1.3},
    # 自我认知强 → metacognitive 权重高
    "反思": {"metacognitive": 1.6, "cognitive": 1.2},
    "自省": {"metacognitive": 1.5},
    "自知": {"metacognitive": 1.4},
}

# 维度 → 个性化追问模板（用 agent 名字和价值观注入）
_DIM_QUESTION_TEMPLATES: Dict[str, List[str]] = {
    "temporal": [
        "5年后回头看，这个选择还成立吗？",
        "10年后你会感谢还是后悔今天这个决定？",
        "这个选择对你的三年目标是加速还是阻碍？",
    ],
    "emotional": [
        "做这个选择后，你的情绪状态会是什么样？",
        "如果只凭直觉，你会怎么选？",
        "这个选择符合你内心真正的感受吗？",
    ],
    "cognitive": [
        "支撑这个判断的关键证据是什么？有哪些反例？",
        "这个判断最容易被什么信息推翻？",
        "你现在掌握的信息足够做出这个决定吗？",
    ],
    "game_theory": [
        "对方/对手在这个局面下会怎么反应？",
        "这个选择对你最不利的情况是什么？",
        "有没有可能达成双赢？",
    ],
    "moral": [
        "如果全世界都知道你这个选择，你会怎么解释？",
        "这个选择损害了谁的利益？",
        "你的底线在哪里，这个选择有没有越线？",
    ],
    "economic": [
        "这个机会成本是什么？你放弃了什么？",
        "这个投入的回报周期是多长？",
        "财务上最坏情况你能承受吗？",
    ],
    "social": [
        "这个选择对你的人际关系会有什么影响？",
        "重要的人会怎么看待你这个决定？",
        "这个选择是出于真实想法还是社会压力？",
    ],
    "dialectical": [
        "支持这个判断的最强论据是什么？",
        "反对这个判断的最强论据是什么？",
        "有没有你还没有考虑到的第三种可能性？",
    ],
    "metacognitive": [
        "你现在判断的置信度是多少？你确定吗？",
        "你有哪些认知偏差可能在影响这个判断？",
        "如果是别人问你，你会给同样的建议吗？",
    ],
    "intuitive": [
        "抛开所有分析，你的第一直觉是什么？",
        "这个直觉背后有没有你还没意识到的经验？",
        "你的直觉和理性分析一致吗？",
    ],
}


def infer_dimension_weights(profile: Dict[str, Any]) -> Dict[str, float]:
    """
    从 agent_profile 推断维度权重调整。
    返回 {dim_id: weight_multiplier}，默认1.0。
    """
    if not profile:
        return {}

    weights: Dict[str, float] = {}
    # 从 values 里提取关键词
    values = profile.get("values", [])
    biases = profile.get("biases", [])
    name = profile.get("name", "")
    decision_style = profile.get("decision_style", "")

    # 合并所有文本供检索
    all_text = " ".join([
        name,
        decision_style,
        *values,
        *biases,
    ]).lower()

    for keyword, dim_weights in _DIMENSION_KEYWORDS.items():
        if keyword.lower() in all_text:
            for dim, w in dim_weights.items():
                weights[dim] = max(weights.get(dim, 1.0), w)

    # biases 降低对应维度权重
    for b in biases:
        b_lower = b.lower()
        for dim in _DIMENSION_KEYWORDS:
            if dim in b_lower:
                weights[dim] = weights.get(dim, 1.0) * 0.7  # 偏差维度降权

    return weights


def build_personalized_prompt(profile: Dict[str, Any], dim_id: str, task_text: str) -> List[str]:
    """
    为指定维度构建个性化追问。
    结合 agent 的名字、价值观、偏差模式，生成该维度专属的深度追问。
    """
    if not profile:
        return []

    name = profile.get("name", "")
    values = profile.get("values", [])
    biases = profile.get("biases", [])
    decision_style = profile.get("decision_style", "")
    val_str = " > ".join(values[:3]) if values else ""

    prompts = []

    # 维度专属追问模板
    templates = _DIM_QUESTION_TEMPLATES.get(dim_id, [])
    if templates:
        # 选择最相关的1条追问（根据 values/decision_style 选）
        style = decision_style.lower()
        if "long" in style or "temporal" in dim_id:
            chosen = templates[0]  # 长期视角
        elif "risk" in style or "game_theory" in dim_id:
            chosen = templates[3] if len(templates) > 3 else templates[0]  # 博弈视角
        elif "moral" in dim_id:
            chosen = templates[0]  # 道德视角
        else:
            chosen = templates[-1]  # 默认直觉/metacognitive 最后一条

        # 注入个人名字和价值观
        chosen = chosen.replace("{name}", name).replace("{values}", val_str)
        if name:
            prompts.append(f"【{name}的视角】{chosen}")
        if biases:
            bias_str = "、".join(biases[:2])
            prompts.append(f"【注意】{name}在{biases[0]}上容易犯错，这次有没有犯？")

    return prompts


def inject_profile_into_dimensions(profile: Dict[str, Any], task_text: str) -> tuple:
    """
    核心问题1修复：biography/experiences → 每个维度的个性化权重和追问。

    返回 (weights: Dict[str, float], prompts: Dict[str, List[str]])
    - weights: 每个维度的权重乘数（>1增强，<1削弱，1.0不变）
    - prompts: 每个维度的追加追问列表

    调用方式：
        weights, prompts = inject_profile_into_dimensions(profile, task_text)
        for dim in dims_to_analyze:
            extra = prompts.get(dim.id, [])
            # 应用权重 ...
    """
    if not profile:
        return {}, {}

    weights = infer_dimension_weights(profile)
    prompts: Dict[str, List[str]] = {}

    for dim_id in _DIM_QUESTION_TEMPLATES:
        dim_prompts = build_personalized_prompt(profile, dim_id, task_text)
        if dim_prompts:
            prompts[dim_id] = dim_prompts

    return weights, prompts


def _inject_profile_questions(profile, task_text):
    """
    兼容旧接口：仅返回 cognitive 维度的追加追问。
    新代码应使用 inject_profile_into_dimensions()。
    """
    _, prompts = inject_profile_into_dimensions(profile, task_text)
    return prompts.get("cognitive", [])