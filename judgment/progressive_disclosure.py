#!/usr/bin/env python3
# judgment/progressive_disclosure.py
# Progressive Disclosure - Hermes Orange-Book
from __future__ import annotations
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
_DIM_SHORT = {
    "cognitive": "认知", "game_theory": "博弈", "economic": "经济",
    "dialectical": "辩证", "emotional": "情绪", "intuitive": "直觉",
    "moral": "道德", "social": "社会", "temporal": "时间",
    "metacognitive": "元认知",
}
@dataclass
class DisclosureResult:
    layer: int; needs_user_confirm: bool; user_prompt: str
    full_result: Optional[Dict]; verdict: Optional[str]
    confidence: Optional[float]; dim_preview: Optional[Dict]
    suggestions: List[str]; reveal_dimensions: bool
def _score(ans: str) -> float:
    if not ans: return 0.0
    s = 0.0
    for kw in ["建议","支持","推荐","可以","值得","鼓励","应该","应当"]:
        if kw in ans: s += 1
    for kw in ["不建议","谨慎","风险","不安","避免","不宜","慎重","警告"]:
        if kw in ans: s += 1
    if "=>" in ans or "结论" in ans: s += 1
    return s
def get_dimension_preview(answers: Dict[str, str]) -> Dict[str, Any]:
    ds = {d: _score(a) for d, a in answers.items()}
    sd = sorted(ds.items(), key=lambda x: x[1], reverse=True)
    top3 = [{"id": d[0], "short": _DIM_SHORT.get(d[0], d[0]), "score": d[1]} for d in sd[:3]]
    bot3 = [{"id": d[0], "short": _DIM_SHORT.get(d[0], d[0]), "score": d[1]} for d in sd[-3:]]
    pro = sum(1 for s in ds.values() if s >= 3)
    con = sum(1 for s in ds.values() if 0 < s < 3)
    return {"top3": top3, "bot3": bot3, "has_contradiction": bool(pro > 0 and con > 0),
            "pro_count": pro, "con_count": con}
def apply_disclosure(task_text, answers, verdict, confidence, full_result, user_wants_full=False) -> DisclosureResult:
    preview = get_dimension_preview(answers)
    contra = ""
    if preview["has_contradiction"]:
        contra = ("[分歧:%d支持/%d谨慎],结论已权衡" % (preview["pro_count"], preview["con_count"]))
    top = "、".join([d["short"] for d in preview["top3"]]) if preview["top3"] else "多维"
    if confidence < 0.40:
        p = ("[置信度%.0f%%,把握不大] " % (confidence*100)) + (verdict[:80] if verdict else "")
        p += "\n\n建议: 1.补充背景 2.告诉更看重什么 3.说说过去类似情况"
        return DisclosureResult(layer=0, needs_user_confirm=True, user_prompt=p,
            full_result=None, verdict=verdict[:80] if verdict else None,
            confidence=confidence, dim_preview=None,
            suggestions=["补充背景信息","告诉我你更看重什么","说说过去类似情况"],
            reveal_dimensions=False)
    if confidence < 0.60:
        p = ("[置信度%.0f%%] " % (confidence*100)) + (verdict[:60] if verdict else "") + "\n" + contra
        p += "\n\n涉及:" + top + "等维度.可以说:「展开」|补充信息|「直接建议」"
        return DisclosureResult(layer=1, needs_user_confirm=True, user_prompt=p,
            full_result=None, verdict=verdict[:80] if verdict else None,
            confidence=confidence, dim_preview=preview,
            suggestions=["展开"+top+"维度分析","补充背景信息","直接给最终建议"],
            reveal_dimensions=False)
    if 0.60 <= confidence < 0.80:
        p = "[结论]" + verdict + "\n置信度:%.0f%%" % (confidence*100) + "\n" + contra
        p += "\n\n涉及:" + top + "\n「展开」|「直接」|补充"
        return DisclosureResult(layer=2, needs_user_confirm=not user_wants_full, user_prompt=p,
            full_result=full_result if user_wants_full else None,
            verdict=verdict, confidence=confidence, dim_preview=preview,
            suggestions=["展开10维度","直接给建议","补充信息"],
            reveal_dimensions=user_wants_full)
    return DisclosureResult(layer=3, needs_user_confirm=False, user_prompt=verdict,
        full_result=full_result, verdict=verdict, confidence=confidence,
        dim_preview=preview, suggestions=[], reveal_dimensions=True)
def format_disclosure(dr: DisclosureResult, include_dims: bool = False) -> str:
    parts = []
    if dr.confidence and dr.confidence >= 0.80: emoji = "OK"
    elif dr.confidence and dr.confidence >= 0.60: emoji = "WA"
    else: emoji = "LO"
    icons = {0: "[L0]", 1: "[L1]", 2: "[L2]", 3: "[L3]"}
    if dr.verdict:
        parts.append(emoji + " " + icons.get(dr.layer,"") + " " + dr.verdict)
        if dr.confidence: parts.append("   conf=%.0f%%" % (dr.confidence*100))
    if dr.dim_preview and dr.dim_preview.get("has_contradiction"):
        parts.append("\n[各维度方向分歧,已综合权衡]")
    if dr.dim_preview and not include_dims:
        top = dr.dim_preview["top3"]
        if top: parts.append("\n涉及:" + "、".join([d["short"] for d in top]))
    if include_dims and dr.full_result and "dimensions" in dr.full_result:
        parts.append("")
        dims = dr.full_result.get("dimensions", {})
        if isinstance(dims, dict):
            def sc(x):
                v = x[1]
                return float(v.get("score",0)) if isinstance(v,dict) else float(v) if isinstance(v,(int,float)) else 0.0
            for dim_id, info in sorted(dims.items(), key=sc, reverse=True):
                v = info.get("score",info) if isinstance(info,dict) else info
                score = float(v) if isinstance(v,(int,float)) else 0.0
                bar = "█" * int(score*10) + "░" * (10 - int(score*10))
                short = _DIM_SHORT.get(dim_id, dim_id)
                parts.append("  %-4s %s %.0f%%" % (short, bar, score*100))
    if dr.needs_user_confirm:
        parts.append(""); parts.append("-" * 28)
        for sg in dr.suggestions: parts.append("  · " + sg)
    return "\n".join(parts)
def detect_user_intent(user_input: str) -> str:
    if not user_input: return "unknown"
    for kw in ["展开","详细","完整","十维","10维","分析","全部","深入","细说"]:
        if kw in user_input: return "expand"
    for kw in ["直接","给建议","结论","总结","精简","简单说","就说"]:
        if kw in user_input: return "direct"
    for kw in ["补充","另外","还有","背景","我是","我情况","但是","不过"]:
        if kw in user_input: return "supplement"
    return "unknown"
