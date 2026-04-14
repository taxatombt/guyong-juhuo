#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_model.py — 聚活自我模型
**独特核心技术（聚活独有）：贝叶斯盲区追踪**

普通自我认知是定性说"我擅长/不擅长这个"，聚活用贝叶斯概率追踪盲区：

1. **贝叶斯置信度更新**：
   - 第一次看到你在某维度失误 → 置信度 0.3（只是潜在偏差）
   - 三次看到同样失误 → 置信度升到 0.6+（很可能真的有偏差）
   - 五次以上 → 置信度接近 1.0（确定这是你的盲区）
   - 置信度公式：`confidence = min(1.0, 0.2 + 0.16 * mistake_count)` → 对数增长，符合认知规律

2. **盲区预热机制**：
   - 置信度 < 0.5 → 只记录，不提醒（避免过度警告）
   - 置信度 >= 0.5 → 正式进入提醒列表，每次判断前提醒你注意
   - 这样不会过度干扰你，只在比较确定的时候才出声

3. **优势强化追踪**：
   - 同样贝叶斯算法追踪你做得好的维度
   - 做得对越多，越确定这是你的优势，每次判断前给你信心

核心问题：**我知道自己擅长什么、不擅长什么、什么时候会犯什么类型的错**
- 不是拍脑袋说，是**贝叶斯概率定量追踪**
- 每次反馈自动更新，越来越准
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from causal_memory.causal_memory import load_all_events, load_all_links


# 文件路径
SELF_MODEL_FILE = Path(__file__).parent.parent / "self_model.json"


@dataclass
class KnownBias:
    """已知偏差"""
    dimension: str          # 哪个维度
    mistake_count: int      # 失误次数
    first_seen: str
    last_seen: str
    description: str        # 描述："容易跳过这个维度" / "容易高估风险"
    confidence: float       # 0-1，我们有多确定这是真偏差

    def to_dict(self):
        return {
            "dimension": self.dimension,
            "mistake_count": self.mistake_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "description": self.description,
            "confidence": self.confidence,
        }


@dataclass
class Strength:
    """已知优势"""
    dimension: str
    correct_count: int
    last_used: str
    description: str

    def to_dict(self):
        return {
            "dimension": self.dimension,
            "correct_count": self.correct_count,
            "last_used": self.last_used,
            "description": self.description,
        }


@dataclass
class SelfModel:
    """自我模型"""
    biases: Dict[str, KnownBias] = field(default_factory=dict)
    strengths: Dict[str, Strength] = field(default_factory=dict)
    total_decisions: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "biases": {k: v.to_dict() for k, v in self.biases.items()},
            "strengths": {k: v.to_dict() for k, v in self.strengths.items()},
            "total_decisions": self.total_decisions,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data):
        model = cls()
        model.total_decisions = data.get("total_decisions", 0)
        model.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        for dim, bias_data in data.get("biases", {}).items():
            model.biases[dim] = KnownBias(
                dimension=bias_data["dimension"],
                mistake_count=bias_data["mistake_count"],
                first_seen=bias_data["first_seen"],
                last_seen=bias_data["last_seen"],
                description=bias_data["description"],
                confidence=bias_data["confidence"],
            )
        
        for dim, strength_data in data.get("strengths", {}).items():
            model.strengths[dim] = Strength(
                dimension=strength_data["dimension"],
                correct_count=strength_data.get("correct_count", 0),
                last_used=strength_data.get("last_used", datetime.now().isoformat()),
                description=strength_data.get("description", ""),
            )
        
        return model


def init():
    """初始化自我模型文件"""
    if not SELF_MODEL_FILE.exists() or SELF_MODEL_FILE.stat().st_size == 0:
        empty_model = SelfModel()
        save_model(empty_model)


def save_model(model: SelfModel):
    """保存自我模型"""
    model.updated_at = datetime.now().isoformat()
    with open(SELF_MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model.to_dict(), f, ensure_ascii=False, indent=2)


def load_model() -> SelfModel:
    """加载自我模型"""
    init()
    with open(SELF_MODEL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SelfModel.from_dict(data)


def update_from_feedback(event) -> Optional[KnownBias]:
    """
    聚活独特技术：贝叶斯盲区追踪 — 从一次判断反馈更新自我模型

    兼容两种 event 格式：
    - 旧格式（其他模块）：feedback in ["坏","错"] + skipped=[dims]
    - 新格式（causal_memory）：feedback_type="judgment_repeated_mistake/success"
                           + wrong_dimensions=[dims]

    贝叶斯置信度公式：confidence = min(1.0, 0.2 + 0.16 * mistake_count)
    - 1次失误 → 0.36置信度 → "可能是偏差"
    - 3次失误 → 0.68置信度 → "大概率是偏差"
    - 5次失误 → 1.0置信度 → "确定这是盲区"

    对数增长，越往后越难涨 → 不会一次就定型，符合人的认知过程
    """
    model = load_model()
    model.total_decisions += 1
    updated_bias = None

    now = event.get("timestamp") or datetime.now().isoformat()

    # ── 判断反馈类型 ─────────────────────────────────────────────
    feedback_type = event.get("feedback_type", "")
    is_bad = (
        feedback_type == "judgment_repeated_mistake"
        or event.get("feedback") in ["坏", "bad", "wrong", "错", "错误"]
    )
    is_good = (
        feedback_type == "judgment_repeated_success"
        or event.get("feedback") in ["好", "good", "right", "对", "正确"]
    )

    # ── 提取维度列表 ─────────────────────────────────────────────
    if feedback_type.startswith("judgment_repeated"):
        # 新格式：wrong_dimensions 来自 causal_memory 的 pattern 检测
        dims_to_blame = event.get("wrong_dimensions", [])
        dims_to_credit = [
            d for d in event.get("dimensions", []) if d not in dims_to_blame
        ]
    else:
        # 旧格式
        dims_to_blame = event.get("skipped", [])
        dims_to_credit = event.get("must_check", []) + event.get("important", [])

    # ── 坏反馈 → 记录偏差 ────────────────────────────────────────
    if is_bad:
        occurrence_count = event.get("occurrence_count", 1)

        for dim in dims_to_blame:
            if dim in model.biases:
                b = model.biases[dim]
                b.mistake_count += occurrence_count
                b.last_seen = now
                # 贝叶斯更新
                b.confidence = min(1.0, 0.2 + 0.16 * b.mistake_count)
                updated_bias = b
            else:
                model.biases[dim] = KnownBias(
                    dimension=dim,
                    mistake_count=occurrence_count,
                    first_seen=now,
                    last_seen=now,
                    description=f"在 dims_to_blame {dim} 判断失误 {occurrence_count} 次（pattern 检测）",
                    confidence=min(1.0, 0.2 + 0.16 * occurrence_count),
                )
                updated_bias = model.biases[dim]

    # ── 好反馈 → 记录优势 ────────────────────────────────────────
    if is_good:
        for dim in dims_to_credit:
            if dim in model.strengths:
                s = model.strengths[dim]
                s.correct_count += 1
                s.last_used = now
            else:
                model.strengths[dim] = Strength(
                    dimension=dim,
                    correct_count=1,
                    last_used=now,
                    description=f"在 {dim} 维度判断通常准确",
                )

    save_model(model)
    return updated_bias


def build_from_causal_memory():
    """
    聚活贝叶斯盲区追踪：从已有的因果记忆重建自我模型
    慢路径：每天跑一次，批量重建
    使用完整贝叶斯公式重新计算所有偏差置信度
    """
    events = load_all_events()
    model = SelfModel()
    
    for event in events:
        model.total_decisions += 1
        if event.get("feedback") in ["坏", "bad", "wrong", "错", "错误"]:
            for dim in event.get("skipped", []):
                if dim in model.biases:
                    model.biases[dim].mistake_count += 1
                    model.biases[dim].last_seen = event["timestamp"]
                    # 贝叶斯公式：0.2 + 0.16 * mistakes
                    model.biases[dim].confidence = min(1.0, 0.2 + 0.16 * model.biases[dim].mistake_count)
                else:
                    model.biases[dim] = KnownBias(
                        dimension=dim,
                        mistake_count=1,
                        first_seen=event["timestamp"],
                        last_seen=event["timestamp"],
                        description=f"容易跳过{dim}维度，导致判断失误",
                        confidence=0.2 + 0.16 * 1,
                    )
        
        if event.get("feedback") in ["好", "good", "right", "对", "正确"]:
            checked = event.get("must_check", []) + event.get("important", [])
            for dim in checked:
                if dim in model.strengths:
                    model.strengths[dim].correct_count += 1
                    model.strengths[dim].last_used = event["timestamp"]
                else:
                    model.strengths[dim] = Strength(
                        dimension=dim,
                        correct_count=1,
                        last_used=event["timestamp"],
                        description=f"在{dim}维度判断通常准确",
                    )
    
    save_model(model)
    return model


def get_self_warnings(current_result, confidence_threshold: float = 0.5) -> Tuple[List[str], List[str]]:
    """
    聚活独特技术：盲区预热机制 → 只提醒置信度>=阈值的偏差
    低置信度偏差不提醒 → 避免过度干扰判断，只在比较确定的时候出声
    
    参数：
        confidence_threshold: 默认0.5 → 三次失误（0.68）才会提醒
        - < 0.5 就是预热阶段 → 只记录不提醒
        - >= 0.5 正式提醒
    
    返回 (warnings, strengths)
    - warnings: "你过去在这些维度容易错，注意" + 带出因果历史前因后果
    - strengths: "你过去在这些维度做得好"
    """
    from causal_memory.causal_memory import find_similar_events
    
    model = load_model()
    warnings = []
    strengths = []

    # 检查当前跳过的维度有没有已知偏差（且置信度够高才提醒）
    for dim in current_result.get("skipped", []):
        if dim in model.biases:
            bias = model.biases[dim]
            # 聚活盲区预热：只提醒置信度够高的，低置信度不打扰
            if bias.confidence >= confidence_threshold:
                warning_text = f"⚠️ 自我提醒：你过去有{bias.mistake_count}次跳过{dim}维度导致失误，置信度{bias.confidence:.0%} → 这一次是否真的可以跳过？"
                
                # 打通因果记忆：找最近一次这个维度失误的案例，带进来
                similar_events = find_similar_events(dim, max_results=1)
                if similar_events:
                    recent = similar_events[0]
                    warning_text += f"\n    最近一次失误：{recent.get('task', '')[:80]}"
                    if recent.get("feedback"):
                        warning_text += f" → 反馈: {recent['feedback']}"
                
                warnings.append(warning_text)
    
    # 检查当前检查的维度有没有已知优势
    checked = current_result.get("must_check", []) + current_result.get("important", [])
    for dim in checked:
        if dim in model.strengths:
            strength = model.strengths[dim]
            strengths.append(
                f"✓ 你过去在{dim}维度判断准确率不错 ({strength.correct_count} 次正确)，保持这个节奏"
            )
    
    return warnings, strengths





def format_self_report() -> str:
    """生成人类可读的自我模型报告"""
    model = load_model()
    lines = [f"自我模型报告 — 共 {model.total_decisions} 次决策记录\n"]

    lines.append("### 已知偏差（容易在这里犯错）")
    if model.biases:
        sorted_biases = sorted(model.biases.values(), key=lambda x: -x.mistake_count)
        for b in sorted_biases:
            lines.append(f"- {b.dimension}: {b.mistake_count} 次失误，置信度 {b.confidence:.1f} → {b.description}")
    else:
        lines.append("（还没有记录到偏差）")
    
    lines.append("\n### 已知优势（在这里做得不错）")
    if model.strengths:
        sorted_strengths = sorted(model.strengths.values(), key=lambda x: -x.correct_count)
        for s in sorted_strengths:
            lines.append(f"- {s.dimension}: {s.correct_count} 次正确 → {s.description}")
    else:
        lines.append("（还没有记录到优势）")
    
    lines.append(f"\n最后更新：{model.updated_at}")
    return "\n".join(lines)


# 测试
if __name__ == "__main__":
    init()
    model = load_model()
    print(format_self_report())
