"""
adversarial.py — 对抗性验证（魔鬼代言人）

模拟反对派视角，超越个体思维的盲点。

原理：
- 人类倾向于找支持自己观点的证据
- 魔鬼代言人强制找反对证据
- 通过对抗性检验，判断更稳健

使用：
    from adversarial import (
        generate_objections,
        validate_decision,
        format_adversarial_report,
    )
    
    objections = generate_objections("要不要辞职创业")
    result = validate_decision("我要辞职创业", objections)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Objection:
    """反对意见"""
    dimension_id: str  # 来自哪个维度
    objection_text: str  # 反对内容
    strength: str  # "strong" | "medium" | "weak"
    evidence: List[str]  # 支持反对的证据
    counter_response: Optional[str]  # 辩护回应


@dataclass
class AdversarialResult:
    """对抗性验证结果"""
    original_decision: str  # 原始决定
    objections: List[Objection]  # 所有反对意见
    strong_objections: List[Objection]  # 强反对（需要认真对待）
    unaddressed: List[Objection]  # 未回应的反对
    overall_score: float  # 整体稳健度 0-1
    verdict: str  # "ADOPT" | "MODIFY" | "REJECT"

    def to_dict(self):
        return {
            "original_decision": self.original_decision,
            "objections": [
                {
                    "dimension_id": o.dimension_id,
                    "objection_text": o.objection_text,
                    "strength": o.strength,
                    "evidence": o.evidence,
                    "counter_response": o.counter_response,
                }
                for o in self.objections
            ],
            "strong_objections": len(self.strong_objections),
            "unaddressed": [o.objection_text for o in self.unaddressed],
            "overall_score": round(self.overall_score, 2),
            "verdict": self.verdict,
        }


# 维度反对意见模板
OBJECTION_TEMPLATES = {
    "cognitive": [
        "这个判断是否受到了近期事件的影响？（近因效应）",
        "你是否只收集了支持自己观点的证据？（确认偏差）",
        "这个判断是基于事实还是基于你的假设？",
    ],
    "game_theory": [
        "对方会怎么反应？你的决策考虑过对方的应对吗？",
        "是否存在第三方玩家的利益被你忽略了？",
        "如果对方也用同样的逻辑，会出现什么均衡？",
    ],
    "economic": [
        "你真的计算过机会成本吗？还是只看了表面收益？",
        "最坏情况的损失你承受得起吗？",
        "是否存在隐性成本被你忽略了？",
    ],
    "dialectics": [
        "主要矛盾是什么？你是否抓住了核心问题？",
        "这个决策是否会引发新的矛盾？",
        "你对问题的判断是否实事求是，还是在自欺？",
    ],
    "emotional": [
        "你现在是否处于强烈的情绪状态中？（恐惧/兴奋/愤怒）",
        "如果冷静下来，你会做出同样的判断吗？",
        "情绪是信号还是噪音？",
    ],
    "intuitive": [
        "你的直觉是否有足够的经验支撑？还是只是感觉？",
        "直觉告诉你什么？你的理性分析支持直觉吗？",
        "你是否在用直觉逃避理性分析的不适？",
    ],
    "moral": [
        "这个决定在道德上是否站得住脚？",
        "如果所有人都这样做，社会会怎样？",
        "你的价值观和这个决定一致吗？",
    ],
    "social": [
        "你是在做对自己最好的决定，还是在做让别人满意的决定？",
        "群体压力是否影响了你的判断？",
        "如果这个决定被公开，你会被别人怎么看？",
    ],
    "temporal": [
        "5年后回看这个决定，你会后悔吗？",
        "你是否在用短期收益换取长期代价？",
        "时间折扣是否让你高估了近期、低估了远期？",
    ],
    "metacognitive": [
        "你意识到自己在用什么思维模式做这个决定吗？",
        "你是否在说服自己而不是分析问题？",
        "你对这个决定的置信度有多高？依据是什么？",
    ],
}


def generate_objections(
    decision: str,
    dimensions: List[str] = None
) -> List[Objection]:
    """
    生成魔鬼代言人的反对意见

    参数:
        decision: 用户决定
        dimensions: 要检验的维度，默认全选
    """
    if dimensions is None:
        dimensions = list(OBJECTION_TEMPLATES.keys())

    objections = []
    for dim_id in dimensions:
        templates = OBJECTION_TEMPLATES.get(dim_id, [])
        for i, template in enumerate(templates[:2]):  # 每维度最多2个反对意见
            # 根据strength分配
            if i == 0:
                strength = "strong"
            elif i == 1:
                strength = "medium"
            else:
                strength = "weak"

            objections.append(Objection(
                dimension_id=dim_id,
                objection_text=template,
                strength=strength,
                evidence=[],
                counter_response=None,
            ))

    return objections


def validate_decision(
    decision: str,
    objections: List[Objection],
    responses: Dict[str, str] = None
) -> AdversarialResult:
    """
    验证决策的稳健度

    参数:
        decision: 原始决定
        objections: 反对意见列表
        responses: {objection_text: counter_response} 用户的回应
    """
    if responses is None:
        responses = {}

    strong_count = 0
    unaddressed = []

    for obj in objections:
        obj.counter_response = responses.get(obj.objection_text)

        # 评估反对强度
        if obj.strength == "strong":
            strong_count += 1

        # 检查是否未回应
        if not obj.counter_response:
            unaddressed.append(obj)

    # 计算整体稳健度
    if not objections:
        overall_score = 1.0
    else:
        addressed_strong = strong_count - len([o for o in unaddressed if o.strength == "strong"])
        overall_score = addressed_strong / max(strong_count, 1) * 0.6  # 强反对占60%

        addressed_weak = sum(1 for o in objections if o.strength != "strong" and o.counter_response)
        overall_score += addressed_weak / max(len(objections) - strong_count, 1) * 0.4

    overall_score = max(0.0, min(1.0, overall_score))

    # 判断verdict
    strong_unaddressed = [o for o in unaddressed if o.strength == "strong"]
    if strong_unaddressed:
        verdict = "REJECT"
    elif overall_score < 0.6:
        verdict = "MODIFY"
    else:
        verdict = "ADOPT"

    return AdversarialResult(
        original_decision=decision,
        objections=objections,
        strong_objections=[o for o in objections if o.strength == "strong"],
        unaddressed=unaddressed,
        overall_score=overall_score,
        verdict=verdict,
    )


def format_adversarial_report(result: AdversarialResult) -> str:
    """格式化对抗性验证报告"""
    lines = ["=== 对抗性验证报告 ===", ""]

    verdict_icon = {"ADOPT": "✅", "MODIFY": "⚠️", "REJECT": "❌"}[result.verdict]
    lines.append(f"判定: {verdict_icon} {result.verdict}")
    lines.append(f"稳健度: {result.overall_score:.0%}")
    lines.append("")

    if result.strong_objections:
        lines.append("【强反对意见】（必须认真对待）：")
        for obj in result.strong_objections:
            lines.append(f"  [{obj.dimension_id}] {obj.objection_text}")
            if obj.counter_response:
                lines.append(f"    ✅ 回应: {obj.counter_response}")
            else:
                lines.append(f"    ⚠️ 未回应")
        lines.append("")

    if result.unaddressed:
        lines.append("【未回应的反对】：")
        for obj in result.unaddressed:
            lines.append(f"  [{obj.dimension_id}] {obj.objection_text}")
        lines.append("")

    return "\n".join(lines)


# 快速验证函数
def quick_validate(decision: str) -> AdversarialResult:
    """一步完成反对意见生成→验证"""
    objections = generate_objections(decision)
    return validate_decision(decision, objections)
