#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
black_swan.py — 黑天鹅压力测试

来源：BruceLanLan/buffett-oracle-analyzer 的黑天鹅测试理念

核心理念：
- 每个判断除了出 verdict，还要问："最坏情况有多坏？"
- 用极端情景对冲后的判断替代纯乐观判断
- 6个维度：下行空间 / 极端情景 / 尾部风险 / 相关性崩溃 / 流动性风险 / 模型失效

用途：
- 高置信度 + 低黑天鹅防御 = 危险 → 降低置信度
- 黑天鹅评分 < 3/6 → 自动加"需对冲"提示
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


# ── 黑天鹅情景库 ─────────────────────────────────────────────────────

BLACK_SWAN_SCENARIOS = [
    {
        "id": "bs_01",
        "name": "市场闪崩",
        "trigger": "标的价格在1-3天内下跌20%以上",
        "impact": "所有头寸面临强制平仓风险，流动性急剧恶化",
        "mitigation": "止损线应能触发，避免持有超过组合5%的单一风险敞口",
    },
    {
        "id": "bs_02",
        "name": "政策突变",
        "trigger": "监管政策/利率/汇率突然改变",
        "impact": "原有逻辑被颠覆，相关资产剧烈波动",
        "mitigation": "避免过度集中单一方向，留有对冲空间",
    },
    {
        "id": "bs_03",
        "name": "黑天鹅事件",
        "trigger": "战争/疫情/重大自然灾害/恐怖袭击",
        "trigger_keywords": ["战争", "疫情", "制裁", "地震", "灾害", "恐怖"],
        "impact": "相关性趋近1，所有资产同跌，风险资产无避风港",
        "mitigation": "组合中应有低相关性资产或现金仓位",
    },
    {
        "id": "bs_04",
        "name": "流动性枯竭",
        "trigger": "市场成交量骤降，买卖价差扩大10倍以上",
        "impact": "无法按合理价格平仓，止损失效",
        "mitigation": "避免交易流动性差的标的，仓位不超过日均成交量的1%",
    },
    {
        "id": "bs_05",
        "name": "模型失效",
        "trigger": "市场结构改变，历史规律不再适用",
        "impact": "基于历史数据的判断全面失准",
        "mitigation": "设置最大连续亏损限制，触发后强制暂停策略",
    },
    {
        "id": "bs_06",
        "name": "对手方违约",
        "trigger": "交易所/券商/做市商出现问题",
        "impact": "资金被冻结，无法转账，无法平仓",
        "mitigation": "分散存放资产，不将所有资金置于单一平台",
    },
]


# ── 黑天鹅评分维度 ─────────────────────────────────────────────────

@dataclass
class BlackSwanAssessment:
    """黑天鹅压力测试结果"""
    scenario_id: str
    scenario_name: str
    relevance: float          # 0.0-1.0，当前判断与该情景的相关程度
    worst_case: str          # 最坏情况描述
    mitigation_status: str    # "covered" / "partial" / "none"
    risk_level: str           # "low" / "medium" / "high" / "critical"
    score: float             # 0.0-1.0，该情景的综合风险评分

    def to_dict(self) -> Dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "relevance": round(self.relevance, 2),
            "worst_case": self.worst_case,
            "mitigation_status": self.mitigation_status,
            "risk_level": self.risk_level,
            "score": round(self.score, 3),
        }


@dataclass
class BlackSwanReport:
    """整体黑天鹅报告"""
    task: str
    timestamp: str
    overall_score: float          # 0.0（安全）- 1.0（极危险）
    risk_level: str               # safe / cautious / dangerous / critical
    assessments: List[BlackSwanAssessment] = field(default_factory=list)
    hedge_suggestions: List[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0  # 原始置信度调整量（负数=降低）

    def to_dict(self) -> Dict:
        return {
            "task": self.task[:100],
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 3),
            "risk_level": self.risk_level,
            "assessments": [a.to_dict() for a in self.assessments],
            "hedge_suggestions": self.hedge_suggestions,
            "confidence_adjustment": round(self.confidence_adjustment, 3),
            "adjusted_confidence_note": (
                f"原始置信度已下调 {-self.confidence_adjustment:.0%} "
                f"（黑天鹅风险评级：{self.risk_level}）"
                if self.confidence_adjustment < 0 else "无需调整"
            ),
        }


def assess_black_swan(task: str, verdict: str, confidence: float,
                      dimensions: List[Dict],
                      market_context: Optional[str] = None) -> BlackSwanReport:
    """
    对一个判断做黑天鹅压力测试。

    流程：
    1. 关键词匹配 → 判断与哪些情景相关
    2. 各情景评估 → relevance × risk → score
    3. 汇总评分 → overall_score
    4. 生成对冲建议

    参数：
        task         — 原始问题
        verdict      — 判断结论
        confidence   — 原始置信度
        dimensions   — 判断维度列表
        market_context — 市场环境备注（可选）

    返回：BlackSwanReport
    """
    now = datetime.now()
    task_lower = task.lower()
    verdict_lower = verdict.lower()

    assessments = []
    high_risk_count = 0
    critical_count = 0

    for scenario in BLACK_SWAN_SCENARIOS:
        relevance = _calc_relevance(task_lower, verdict_lower, scenario)
        if relevance < 0.1:
            continue  # 无关情景跳过

        # 检查 mitigation 状态（根据 dimensions 推断）
        mitigation = _assess_mitigation(relevance, dimensions, scenario)

        # 风险评分 = relevance × impact_factor
        impact_factor = 1.0 if mitigation["status"] == "none" else 0.5 if mitigation["status"] == "partial" else 0.2
        score = min(relevance * impact_factor * 1.5, 1.0)  # 上限1.0

        risk_level = _score_to_level(score)
        if risk_level == "high":
            high_risk_count += 1
        elif risk_level == "critical":
            critical_count += 1

        assessments.append(BlackSwanAssessment(
            scenario_id=scenario["id"],
            scenario_name=scenario["name"],
            relevance=relevance,
            worst_case=scenario["impact"],
            mitigation_status=mitigation["status"],
            risk_level=risk_level,
            score=score,
        ))

    # 整体评分 = 最高单项分数 或 加权平均（取较高者）
    if assessments:
        max_score = max(a.score for a in assessments)
        avg_score = sum(a.score for a in assessments) / len(assessments)
        overall = max(max_score, avg_score)  # 保守：取较高的
    else:
        max_score = 0.0
        avg_score = 0.0
        overall = 0.0

    risk_level = _score_to_level(overall)

    # 置信度调整（黑天鹅风险越高 → 降置信度越多）
    if overall >= 0.7:
        adj = -0.15
        level = "critical"
    elif overall >= 0.5:
        adj = -0.10
        level = "dangerous"
    elif overall >= 0.3:
        adj = -0.05
        level = "cautious"
    else:
        adj = 0.0
        level = "safe"

    # 生成对冲建议
    suggestions = _generate_suggestions(assessments, overall)

    return BlackSwanReport(
        task=task,
        timestamp=now.isoformat(),
        overall_score=overall,
        risk_level=level,
        assessments=assessments,
        hedge_suggestions=suggestions,
        confidence_adjustment=adj,
    )


def _calc_relevance(task: str, verdict: str, scenario: Dict) -> float:
    """计算情景与当前判断的相关程度"""
    trigger_kw = scenario.get("trigger_keywords", [])
    if not trigger_kw:
        # 用 trigger 文本提取关键词
        trigger = scenario.get("trigger", "")
        trigger_kw = [t.strip("，。、") for t in trigger if len(t.strip()) >= 2]

    text = task + " " + verdict
    matches = sum(1 for kw in trigger_kw if kw in text)
    if not trigger_kw:
        return 0.0
    return min(matches / len(trigger_kw) * 2, 1.0)  # 有1个匹配=0.5，有2个=1.0


def _assess_mitigation(relevance: float, dimensions: List[Dict],
                       scenario: Dict) -> Dict:
    """
    根据 dimensions 推断 mitigation 状态。

    逻辑：
    - 有 game_theory 维度且分数高 → "covered"（考虑了对手风险）
    - 有 economic 维度且分数高 → "partial"（有成本意识）
    - 有 temporal 维度且分数高 → "partial"（考虑了时间维度风险）
    - 其他 → "none"
    """
    if relevance < 0.3:
        return {"status": "none", "reason": "相关性低，无需评估"}

    dim_map = {d.get("id", ""): d.get("score", 0) for d in dimensions}
    game_theory = dim_map.get("game_theory", 0)
    economic = dim_map.get("economic", 0)
    temporal = dim_map.get("temporal", 0)
    metacognitive = dim_map.get("metacognitive", 0)

    if scenario["id"] in ("bs_01", "bs_03", "bs_04"):
        # 市场崩溃类 → game_theory 高分才 cover
        if game_theory >= 0.75:
            return {"status": "covered", "reason": "博弈维度高分，考虑了极端对手"}
        elif game_theory >= 0.50:
            return {"status": "partial", "reason": "部分覆盖"}
        return {"status": "none", "reason": "未覆盖对手方极端行为风险"}

    if scenario["id"] in ("bs_02", "bs_05"):
        # 政策/模型失效类 → metacognitive 高分才 cover
        if metacognitive >= 0.75:
            return {"status": "covered", "reason": "元认知高分，预见了自身盲点"}
        elif metacognitive >= 0.50:
            return {"status": "partial", "reason": "部分覆盖"}
        return {"status": "none", "reason": "未覆盖模型/政策失效风险"}

    if scenario["id"] in ("bs_06",):
        # 流动性/对手方 → economic + temporal 联合评估
        if economic >= 0.70 and temporal >= 0.60:
            return {"status": "covered", "reason": "经济+时间维度联合覆盖"}
        elif economic >= 0.50 or temporal >= 0.50:
            return {"status": "partial", "reason": "部分覆盖"}
        return {"status": "none", "reason": "未覆盖流动性风险"}

    return {"status": "none", "reason": "无 mitigation 信息"}


def _score_to_level(score: float) -> str:
    if score >= 0.70: return "critical"
    if score >= 0.50: return "high"
    if score >= 0.30: return "medium"
    return "low"


def _generate_suggestions(assessments: List[BlackSwanAssessment],
                          overall: float) -> List[str]:
    """根据评估生成对冲建议"""
    suggestions = []
    high_risk = [a for a in assessments if a.risk_level in ("high", "critical")]

    if overall >= 0.70:
        suggestions.append("⚠️ 黑天鹅风险极高，建议暂缓执行，补充更多信息")

    for a in high_risk:
        if a.mitigation_status == "none":
            if a.scenario_id == "bs_01":
                suggestions.append(f"📉 [{a.scenario_name}] 建议设置硬止损，仓位不超过5%")
            elif a.scenario_id == "bs_03":
                suggestions.append(f"🌊 [{a.scenario_name}] 建议配置10%以上现金或低相关性资产")
            elif a.scenario_id == "bs_05":
                suggestions.append(f"🤖 [{a.scenario_name}] 建议设置最大连续亏损熔断，连续2笔亏损后暂停")
            elif a.scenario_id == "bs_04":
                suggestions.append(f"💧 [{a.scenario_name}] 建议只交易日成交量>1000万的标的")

    if not suggestions:
        suggestions.append("✅ 各黑天鹅情景已有基本覆盖，继续执行")
    return suggestions


def format_black_swan_report(report: BlackSwanReport) -> str:
    """把 BlackSwanReport 格式化为可读文本"""
    lines = []
    risk_icon = {"safe": "✅", "cautious": "🟡", "dangerous": "🟠", "critical": "🔴"}
    icon = risk_icon.get(report.risk_level, "⚪")

    lines.append(f"{icon} 黑天鹅压力测试 | 风险等级：{report.risk_level.upper()}")
    lines.append(f"   整体风险评分：{report.overall_score:.0%}")
    lines.append(f"   置信度调整：{report.confidence_adjustment:+.0%}")

    if report.assessments:
        lines.append("")
        lines.append("   情景评估：")
        for a in report.assessments:
            level_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
            lines.append(
                f"   {level_icon.get(a.risk_level,'⚪')} {a.scenario_name}"
                f"（相关{a.relevance:.0%} | 缓解{a.mitigation_status}）"
            )
            lines.append(f"      最坏：{a.worst_case[:60]}")

    if report.hedge_suggestions:
        lines.append("")
        for s in report.hedge_suggestions:
            lines.append(f"   {s}")

    return "\n".join(lines)
