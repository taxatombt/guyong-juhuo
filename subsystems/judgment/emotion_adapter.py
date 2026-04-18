# -*- coding: utf-8 -*-
"""
emotion_adapter.py — Emotion × Judgment 集成适配器

PAD 维度:
  P (Pleasure)    愉悦度: -1~+1
  A (Arousal)    激活度: -1~+1
  D (Dominance)  支配度: -1~+1

核心接口: get_emotion_modulation(pad) -> EmotionModulation
"""

from typing import Dict, List
from dataclasses import dataclass

_EMOTION_MAP = {
    (">", ">", ">"): "excitement",
    ("<", ">", "<"): "anxiety",
    ("<", ">", ">"): "anger",
    (">", ">", "<"): "fear",
    (">", "<", "_"): "joy",
    ("<", "<", "_"): "sadness",
}

def pad_to_emotion_label(pad: Dict[str, float]) -> str:
    P, A, D = pad.get("P", 0.0), pad.get("A", 0.0), pad.get("D", 0.0)
    th = 0.2
    tp = ">" if P > th else "<" if P < -th else "_"
    ta = ">" if A > th else "<" if A < -th else "_"
    td = ">" if D > th else "<" if D < -th else "_"
    # 中性（全部 "_"）→ calm
    if (tp, ta, td) == ("_", "_", "_"):
        return "calm"
    # 精确匹配
    if (tp, ta, td) in _EMOTION_MAP:
        return _EMOTION_MAP[(tp, ta, td)]
    # 补充匹配：P>0且A<0 → joy（愉悦但低激活，如平静满足）
    if tp == ">" and ta == "<":
        return "joy"
    # 补充匹配：P<0且A<0 → sadness（低愉悦低激活）
    if tp == "<" and ta == "<":
        return "sadness"
    # 部分匹配（忽略 "_" 位置）
    for pattern, label in _EMOTION_MAP.items():
        if all(a == b or b == "_" for a, b in zip(pattern, (tp, ta, td))):
            return label
    return "calm"

_EMOTION_MODS = {
    "anxiety": {
        "cognitive": 0.70, "game_theory": 1.15, "economic": 0.85,
        "dialectical": 0.80, "emotional": 1.30, "intuitive": 0.75,
        "moral": 0.90, "social": 0.85, "temporal": 1.30, "metacognitive": 0.80,
    },
    "excitement": {
        "cognitive": 1.20, "game_theory": 1.10, "economic": 1.20,
        "dialectical": 1.05, "emotional": 1.15, "intuitive": 1.15,
        "moral": 0.80, "social": 1.05, "temporal": 0.90, "metacognitive": 0.85,
    },
    "anger": {
        "cognitive": 0.70, "game_theory": 1.10, "economic": 0.85,
        "dialectical": 0.75, "emotional": 1.30, "intuitive": 0.80,
        "moral": 1.30, "social": 1.15, "temporal": 0.85, "metacognitive": 0.70,
    },
    "fear": {
        "cognitive": 1.20, "game_theory": 1.10, "economic": 0.75,
        "dialectical": 0.90, "emotional": 1.20, "intuitive": 0.70,
        "moral": 0.95, "social": 0.80, "temporal": 1.30, "metacognitive": 0.75,
    },
    "joy": {
        "cognitive": 1.20, "game_theory": 1.05, "economic": 1.15,
        "dialectical": 1.10, "emotional": 1.10, "intuitive": 1.10,
        "moral": 1.05, "social": 1.10, "temporal": 0.80, "metacognitive": 1.05,
    },
    "sadness": {
        "cognitive": 0.80, "game_theory": 0.90, "economic": 0.85,
        "dialectical": 0.90, "emotional": 1.15, "intuitive": 0.85,
        "moral": 1.05, "social": 1.10, "temporal": 0.80, "metacognitive": 0.85,
    },
    "calm": {
        "cognitive": 1.10, "game_theory": 1.05, "economic": 1.05,
        "dialectical": 1.10, "emotional": 0.90, "intuitive": 1.05,
        "moral": 1.10, "social": 1.00, "temporal": 1.00, "metacognitive": 1.15,
    },
}

_EMOTION_SCALE = {
    "anxiety": 0.30, "excitement": 0.25, "anger": 0.30,
    "fear": 0.25, "joy": 0.20, "sadness": 0.20, "calm": 0.10,
}

_EMOTION_HINTS = {
    "anxiety": "【情绪提醒】当前焦虑状态。请降低认知依赖，加强辩证分析，警惕信息不足导致误判，引入元认知检查。",
    "excitement": "【情绪提醒】当前兴奋状态。请警惕过度乐观，保持辩证审视，核查风险假设。",
    "anger": "【情绪提醒】当前愤怒状态。请强制引入冷静视角，引入外部评估，警惕愤怒驱动的决定。",
    "fear": "【情绪提醒】当前恐惧状态。请警惕过度短视，引入长期视角，理性区分真实风险与想象风险。",
    "joy": "【情绪提醒】当前愉悦状态。请利用认知优势，保持开放心态，警惕轻视潜在风险。",
    "sadness": "【情绪提醒】当前低落状态。请警惕消极偏差，主动寻找积极因素，避免低估机会价值。",
    "calm": "【情绪提醒】当前平静状态。适合深度分析，可信任认知维度判断，同时保持适度审查。",
}

_EMOTION_CONF = {
    "anxiety": -0.20, "excitement": +0.05, "anger": -0.25,
    "fear": -0.15, "joy": +0.10, "sadness": -0.15, "calm": +0.05,
}


@dataclass
class EmotionModulation:
    emotion_label: str
    pad: Dict[str, float]
    intensity: float
    dim_mods: Dict[str, float]
    prompt_hint: str
    confidence_adjustment: float
    recommended_dims: List[str]
    suppressed_dims: List[str]


def get_emotion_modulation(pad: Dict[str, float]) -> EmotionModulation:
    P, A, D = pad.get("P", 0.0), pad.get("A", 0.0), pad.get("D", 0.0)
    label = pad_to_emotion_label(pad)
    intensity = min(1.0, (abs(P) + abs(A) + abs(D)) / 3.0 * 1.5)
    base_mods = _EMOTION_MODS.get(label, {})
    dim_mods = {}
    scale = _EMOTION_SCALE.get(label, 0.15)
    # 强度决定情绪效应的权重: intensity=1.0 → 完全体情绪调制
    # 例如: anxiety时 cognitive=0.7 → intensity=1.0时 = 0.70; intensity=0时 = 1.0
    for dim, base in base_mods.items():
        val = 1.0 + (base - 1.0) * intensity
        dim_mods[dim] = round(max(0.7, min(1.3, val)), 3)
    # 其余维度不受情绪影响
    for dim in ["cognitive", "game_theory", "economic", "dialectical",
                "emotional", "intuitive", "moral", "social", "temporal", "metacognitive"]:
        if dim not in dim_mods:
            dim_mods[dim] = 1.0
    recommended = [d for d, v in dim_mods.items() if v > 1.05]
    suppressed = [d for d, v in dim_mods.items() if v < 0.95]
    return EmotionModulation(
        emotion_label=label,
        pad=pad,
        intensity=round(intensity, 3),
        dim_mods=dim_mods,
        prompt_hint=_EMOTION_HINTS.get(label, ""),
        confidence_adjustment=_EMOTION_CONF.get(label, 0.0),
        recommended_dims=recommended,
        suppressed_dims=suppressed,
    )
