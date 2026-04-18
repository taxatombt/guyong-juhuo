"""
dynamic_weights.py — 维度权重动态调整 + Auto-evolver 自动进化

根据任务类型动态调整权重权重，避免"一把尺子所有问题"。

Auto-evolver 原理：
- 每次决策后记录结果（对/错）
- 根据反馈自动调整各维度权重
- 长期沉淀 → 权重自动适应一个人的判断风格
- 无需用户手动反馈，形成自我改进闭环

Usage:
    from judgment.dynamic_weights import (
        get_dynamic_weights,
        get_task_complexity,
        update_weights_from_outcome,  # Auto-evolver
        get_evolved_weights,
        get_evolution_summary,
    )
"""

import json
import os
import time
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field, asdict


@dataclass
class WeightConfig:
    """权重配置"""
    dimension_id: str
    base_weight: float  # 基础权重
    task_type_weights: Dict[str, float]  # 不同任务类型的权重
    description: str


# 默认权重配置
DEFAULT_WEIGHTS = {
    "cognitive": WeightConfig(
        dimension_id="cognitive",
        base_weight=1.0,
        task_type_weights={
            "decision": 1.5,  # 决策类任务认知更重要
            "analysis": 2.0,  # 分析类任务
            "risk": 1.5,
        },
        description="认知心理学：偏差检测",
    ),
    "game_theory": WeightConfig(
        dimension_id="game_theory",
        base_weight=0.8,
        task_type_weights={
            "negotiation": 2.0,  # 谈判类
            "competition": 2.0,  # 竞争类
            "conflict": 1.5,
        },
        description="博弈论：多方利益",
    ),
    "economic": WeightConfig(
        dimension_id="economic",
        base_weight=1.0,
        task_type_weights={
            "investment": 2.0,  # 投资类
            "career": 1.5,  # 职业类
            "money": 1.5,
        },
        description="经济学：机会成本",
    ),
    "dialectical": WeightConfig(
        dimension_id="dialectical",
        base_weight=1.0,
        task_type_weights={
            "strategy": 1.5,  # 战略类
            "conflict": 1.5,
        },
        description="辩证法：矛盾分析",
    ),
    "emotional": WeightConfig(
        dimension_id="emotional",
        base_weight=0.8,
        task_type_weights={
            "relationship": 2.0,  # 关系类
            "personal": 1.5,  # 个人情感
        },
        description="情绪智能",
    ),
    "intuitive": WeightConfig(
        dimension_id="intuitive",
        base_weight=0.6,
        task_type_weights={
            "creative": 1.5,  # 创意类
            "quick": 1.0,  # 需要快速决策
        },
        description="直觉判断",
    ),
    "moral": WeightConfig(
        dimension_id="moral",
        base_weight=0.8,
        task_type_weights={
            "ethics": 2.0,  # 伦理类
            "principle": 1.5,
        },
        description="道德推理",
    ),
    "social": WeightConfig(
        dimension_id="social",
        base_weight=0.8,
        task_type_weights={
            "team": 2.0,  # 团队类
            "reputation": 1.5,  # 声誉类
            "social": 1.5,
        },
        description="社会意识",
    ),
    "temporal": WeightConfig(
        dimension_id="temporal",
        base_weight=0.7,
        task_type_weights={
            "long_term": 2.0,  # 长期规划类
            "career": 1.5,
        },
        description="时间折扣",
    ),
    "metacognitive": WeightConfig(
        dimension_id="metacognitive",
        base_weight=0.5,
        task_type_weights={
            "learning": 1.5,  # 学习类
            "reflection": 1.5,
        },
        description="元认知",
    ),
}


# 任务类型检测关键词
TASK_TYPE_KEYWORDS = {
    "decision": ["选择", "决定", "选哪个", "怎么办", "要不要", "怎么选"],
    "analysis": ["分析", "原因", "为什么", "理解", "成本"],
    "risk": ["风险", "冒险", "万一", "可能会输", "不确定"],
    "investment": ["投资", "理财", "存钱", "收益", "回报"],
    "career": ["工作", "职业", "跳槽", "转行", "发展"],
    "relationship": ["感情", "关系", "朋友", "家人", "交往"],
    "negotiation": ["谈判", "议价", "谈", "合作"],
    "competition": ["竞争", "比赛", "对手", "赢"],
    "creative": ["创造", "创新", "设计", "想法"],
    "ethics": ["道德", "对错", "应该", "不应该"],
    "long_term": ["长期", "长远", "以后", "规划"],
    "quick": ["快", "赶紧", "马上", "来不及"],
    "team": ["团队", "大家", "合作", "公司"],
    "social": ["大家怎么看", "社会", "名声"],
    "strategy": ["战略", "策略", "全局"],
    "learning": ["学习", "成长", "提升"],
}


def detect_task_types(text: str) -> List[str]:
    """检测任务类型"""
    text_lower = text.lower()
    detected = []

    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(task_type)

    # 默认返回 decision
    if not detected:
        detected = ["decision"]

    return detected


def get_task_complexity(text: str) -> str:
    """
    判断任务复杂度

    返回: "simple" | "normal" | "complex" | "critical"
    """
    complexity_indicators = {
        "simple": ["简单", "小事", "随便", "无所谓"],
        "normal": ["比较重要", "中等", "一般"],
        "complex": ["复杂", "纠结", "两难", "困难"],
        "critical": ["人生", "重大", "一辈子", "跳槽", "转行", "创业", "结婚"],
    }

    scores = {"simple": 0, "normal": 0, "complex": 0, "critical": 0}

    for complexity, indicators in complexity_indicators.items():
        for ind in indicators:
            if ind in text:
                scores[complexity] += 1

    # 返回得分最高的
    return max(scores, key=scores.get)


def get_dynamic_weights(
    task_text: str,
    base_weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    根据任务类型获取动态权重

    参数:
        task_text: 任务描述
        base_weights: 可选的基础权重映射 {dimension_id: weight}
    """
    task_types = detect_task_types(task_text)
    complexity = get_task_complexity(task_text)

    # 计算复杂度乘数
    complexity_multiplier = {
        "simple": 0.5,
        "normal": 1.0,
        "complex": 1.5,
        "critical": 2.0,
    }[complexity]

    # 如果没有提供基础权重，就使用默认权重
    if base_weights is None:
        base_weights = {dim_id: config.base_weight for dim_id, config in DEFAULT_WEIGHTS.items()}

    # 计算动态权重
    dynamic_weights = {}

    for dim_id, config in DEFAULT_WEIGHTS.items():
        # 从基础权重出发
        weight = base_weights.get(dim_id, config.base_weight)

        # 根据任务类型调整
        for task_type in task_types:
            if task_type in config.task_type_weights:
                weight *= config.task_type_weights[task_type]

        # 根据复杂度调整
        weight *= complexity_multiplier

        dynamic_weights[dim_id] = weight

    # 归一化
    total = sum(dynamic_weights.values())
    if total > 0:
        dynamic_weights = {k: v / total for k, v in dynamic_weights.items()}

    return dynamic_weights


def get_weighted_dimensions(task_text: str, top_n: int = 5) -> List[str]:
    """
    获取权重最高的维度

    参数:
        task_text: 任务描述
        top_n: 返回前N个
    """
    weights = get_dynamic_weights(task_text)
    sorted_dims = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    return [dim_id for dim_id, _ in sorted_dims[:top_n]]


def format_weight_report(task_text: str) -> str:
    """格式化权重报告"""
    task_types = detect_task_types(task_text)
    complexity = get_task_complexity(task_text)
    weights = get_dynamic_weights(task_text)

    lines = ["=== 动态权重报告 ===", ""]
    lines.append(f"检测到的任务类型: {', '.join(task_types)}")
    lines.append(f"任务复杂度: {complexity}")
    lines.append("")
    lines.append("维度权重（从高到低）:")

    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    for dim_id, w in sorted_weights:
        bar = "█" * int(w * 50)
        lines.append(f"  {dim_id:16s} {w:.3f}  {bar}")
    return "\n".join(lines)


# =============================================================================
# Auto-evolver: 反馈驱动的权重自动进化
# =============================================================================

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
EVO_FILE = os.path.join(WEIGHTS_DIR, "evolved_weights.json")
LEARNING_RATE = 0.15  # 学习率：每次反馈更新15%的误差
MAX_HISTORY = 100  # 最多保留 100 条反馈记录


def _load_evo_data() -> dict:
    """加载进化数据"""
    if os.path.exists(EVO_FILE):
        try:
            with open(EVO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "feedbacks": [],      # [{task, dims_checked, outcome, timestamp}, ...]
        "weight_adjustments": {},  # {dim_id: adjustment_value}
        "total_updates": 0,
        "last_updated": None,
    }


def _save_evo_data(data: dict):
    """保存进化数据"""
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    with open(EVO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_weights_from_outcome(
    task_text: str,
    dims_checked: List[str],
    outcome: Literal["good", "bad", "neutral"] = "neutral",
) -> dict:
    """
    Auto-evolver 核心：根据决策结果自动更新维度权重
    
    逻辑：
    - 决策结果好 → 参与决策的维度权重上涨
    - 决策结果坏 → 参与决策的维度权重下降
    - 使用指数移动平均 adjustment = lr * delta + (1-lr) * prev
    
    参数：
        task_text: 任务描述（用于检测任务类型）
        dims_checked: 本次决策中实际检查了哪些维度
        outcome: 结果 good | bad | neutral
    
    返回：
        {
            "updated": True,
            "adjustments": {dim_id: delta, ...},
            "total_updates": int,
        }
    """
    if outcome == "neutral" or not dims_checked:
        return {"updated": False, "adjustments": {}, "total_updates": 0}
    
    # 检测任务类型，决定哪些维度受影响更大
    task_types = detect_task_types(task_text)
    
    # outcome映射：good=+1, bad=-1, neutral=0
    delta_map = {"good": 1.0, "bad": -1.0, "neutral": 0.0}
    delta = delta_map.get(outcome, 0.0)
    
    # 加载进化数据
    evo = _load_evo_data()
    
    # 对每个参与检查的维度更新调整值
    adjustments = {}
    for dim_id in dims_checked:
        prev = evo["weight_adjustments"].get(dim_id, 0.0)
        new_adj = LEARNING_RATE * delta + (1 - LEARNING_RATE) * prev
        evo["weight_adjustments"][dim_id] = new_adj
        adjustments[dim_id] = round(new_adj - prev, 4)
    
    # 记录反馈
    evo["feedbacks"].append({
        "task": task_text[:100],
        "dims_checked": dims_checked,
        "outcome": outcome,
        "timestamp": time.time(),
    })
    
    # 剪枝历史
    if len(evo["feedbacks"]) > MAX_HISTORY:
        evo["feedbacks"] = evo["feedbacks"][-MAX_HISTORY:]
    
    evo["total_updates"] += 1
    evo["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    _save_evo_data(evo)
    
    return {
        "updated": True,
        "adjustments": adjustments,
        "total_updates": evo["total_updates"],
        "evolved_weights": get_evolved_weights(),
    }


def get_evolved_weights(task_text: Optional[str] = None) -> Dict[str, float]:
    """
    获取进化后的权重（包含动态调整 + Auto-evolver 反馈调整）
    
    参数：
        task_text: 可选，用于计算动态权重
    
    返回：
        {dim_id: weight, ...} 归一化后的权重
    """
    evo = _load_evo_data()
    adjustments = evo.get("weight_adjustments", {})
    
    # 基础权重（使用动态权重或默认权重）
    if task_text:
        base = get_dynamic_weights(task_text)
    else:
        base = {dim_id: cfg.base_weight for dim_id, cfg in DEFAULT_WEIGHTS.items()}
    
    # 加上进化调整
    evolved = {}
    for dim_id, base_w in base.items():
        adj = adjustments.get(dim_id, 0.0)
        # adjustment范围 [-1, 1]，映射到权重调整 [-30%, +30%]
        evolved[dim_id] = base_w * (1 + adj * 0.3)
    
    # 归一化
    total = sum(evolved.values())
    if total > 0:
        evolved = {k: v / total for k, v in evolved.items()}
    
    return evolved


def get_evolution_summary() -> dict:
    """
    获取进化摘要，用于诊断：
    
    返回：
        {
            "total_feedbacks": int,
            "total_updates": int,
            "last_updated": str,
            "active_adjustments": {dim_id: adj, ...},
            "recent_feedbacks": [dict, ...],
        }
    """
    evo = _load_evo_data()
    return {
        "total_feedbacks": len(evo["feedbacks"]),
        "total_updates": evo["total_updates"],
        "last_updated": evo.get("last_updated"),
        "active_adjustments": {
            k: round(v, 4)
            for k, v in evo.get("weight_adjustments", {}).items()
            if abs(v) > 0.001
        },
        "recent_feedbacks": evo["feedbacks"][-5:],
    }
