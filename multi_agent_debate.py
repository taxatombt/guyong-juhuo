"""
multi_agent_debate.py — 多AI视角辩论

从不同立场辩论同一个问题，减少盲点
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Position:
    """立场"""
    name: str
    description: str
    key_points: List[str]
    confidence: float


@dataclass
class DebateResult:
    """辩论结果"""
    original_position: Position
    pro: List[Position]
    con: List[Position]
    synthesis: str
    verdict: str  # "STRONG_PRO" / "WEAK_PRO" / "NEUTRAL" / "WEAK_CON" / "STRONG_CON"


# 预设多种立场
STANDARDS_POSITIONS = [
    {
        "name": "倡导者",
        "description": "站在支持者角度，列出所有支持理由",
    },
    {
        "name": "反对者",
        "description": "站在反对者角度，列出所有反对理由",
    },
    {
        "name": "中立观察者",
        "description": "不偏不倚，看双方论证强度",
    },
    {
        "name": "五年后复盘者",
        "description": "站在未来五年后看今天这个决策",
    },
    {
        "name": "魔鬼代言人",
        "description": "专门找漏洞，就算同意也要反对",
    },
]


def generate_positions(decision_text: str) -> List[Position]:
    """为决策生成多立场"""
    positions = []
    for sp in STANDARDS_POSITIONS:
        positions.append(Position(
            name=sp["name"],
            description=sp["description"],
            key_points=[],
            confidence=0.5
        ))

    return positions


def synthesize_debate(positions: List[Position], original: Position) -> Dict:
    """综合辩论结果"""
    pro_count = sum(1 for p in positions if p.confidence > 0.6 and p.name != "倡导者")
    con_count = sum(1 for p in positions if p.confidence > 0.6 and p.name in ["反对者", "魔鬼代言人"])

    if pro_count > con_count * 2:
        verdict = "STRONG_PRO"
    elif pro_count > con_count:
        verdict = "WEAK_PRO"
    elif con_count > pro_count * 2:
        verdict = "STRONG_CON"
    elif con_count > pro_count:
        verdict = "WEAK_CON"
    else:
        verdict = "NEUTRAL"

    strongest_pro = max([p for p in positions if p.name in ["倡导者"]], key=lambda x: x.confidence, default=None)
    strongest_con = max([p for p in positions if p.name in ["反对者", "魔鬼代言人"]], key=lambda x: x.confidence, default=None)

    return {
        "verdict": verdict,
        "strongest_pro": strongest_pro.key_points[0] if strongest_pro and strongest_pro.key_points else None,
        "strongest_con": strongest_con.key_points[0] if strongest_con and strongest_con.key_points else None,
        "pro_count": pro_count,
        "con_count": con_count,
    }


def format_debate_result(result: DebateResult) -> str:
    """格式化辩论结果"""
    lines = ["🗳️ 【多视角辩论】", ""]

    lines.append(f"原始立场: {result.original_position.name} — {result.original_position.description}")
    lines.append("")

    if result.pro:
        lines.append("✅ 支持:")
        for p in result.pro:
            lines.append(f"  • {p.name}: {p.description}")
            for point in p.key_points[:2]:
                lines.append(f"    - {point}")
        lines.append("")

    if result.con:
        lines.append("❌ 反对:")
        for p in result.con:
            lines.append(f"  • {p.name}: {p.description}")
            for point in p.key_points[:2]:
                lines.append(f"    - {point}")
        lines.append("")

    lines.append(f"综合结论: {result.verdict}")
    lines.append(f"  {result.synthesis}")
    lines.append("")

    return "\n".join(lines)


def run_debate(decision_text: str, llm_call=None) -> DebateResult:
    """
    运行完整辩论

    如果 llm_call 提供，会让LLM生成每个立场的论点；否则返回空结构
    """
    original = Position(
        name="原始决策",
        description=decision_text,
        key_points=[],
        confidence=0.5
    )

    positions = generate_positions(decision_text)
    pro = []
    con = []

    # 如果没有LLM回调，只返回结构
    if not llm_call:
        return DebateResult(
            original_position=original,
            pro=pro,
            con=con,
            synthesis="请使用LLM生成各立场论点",
            verdict="NEUTRAL"
        )

    # 完整流程需要LLM逐立场生成 -> 这里留接口给调用方
    synth = synthesize_debate(positions, original)

    return DebateResult(
        original_position=original,
        pro=pro,
        con=con,
        synthesis=f"综合: {synth['verdict']},  pro={synth['pro_count']} con={synth['con_count']}",
        verdict=synth["verdict"]
    )
