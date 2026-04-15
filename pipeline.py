# -*- coding: utf-8 -*-
"""
guyong-juhuo Pipeline 整合 v2

Usage:
    from judgment.pipeline import check10d_full, PipelineConfig, format_full_report
    result = check10d_full("要不要辞职创?, agent_profile_name="<persona>")
    print(format_full_report(result))
"""
import time
from typing import Optional

from judgment.router import check10d_run
from judgment.dynamic_weights import get_dynamic_weights, get_task_complexity, detect_task_types
from judgment.confidence import (
    assess_all_confidences, get_low_confidence_dimensions,
    build_layered_verdict, format_layered_verdict,
    counterfactual_hindsight, format_hindsight,
)
from adversarial import generate_objections
from qiushi_integration import quick_qiushi_check
from embedding_match import find_similar_decisions
from lesson_recognition import get_pattern_warnings
from profile_evolution import get_blind_spots
from profile import check_goals_alignment
from outcome_tracker import start_tracking
from causal_memory.causal_chain import build_causal_chain
from recursive_trigger import recursive_probe
from judgment.metacognitive import metacognitive_review
from multi_agent_debate import run_debate
from trace_context import trace_call


class PipelineConfig:
    def __init__(
        self,
        agent_profile_name: Optional[str] = None,
        enable_adversarial: bool = True,
        enable_qiushi: bool = True,
        enable_embedding: bool = True,
        enable_lessons: bool = True,
        confidence_threshold: float = 0.5,
        agent_profile: Optional[dict] = None,
        complexity: Optional[str] = None,
        enable_trace: bool = False,
    ):
        self.agent_profile_name = agent_profile_name
        self.enable_adversarial = enable_adversarial
        self.enable_qiushi = enable_qiushi
        self.enable_embedding = enable_embedding
        self.enable_lessons = enable_lessons
        self.confidence_threshold = confidence_threshold
        self.agent_profile = agent_profile
        self.complexity = complexity
        self.enable_trace = enable_trace


def check10d_full(task_text: str, config: Optional[PipelineConfig] = None, **kwargs) -> dict:
    """
    完整 Pipeline：串起所有模块的判断入口
    """
    start_time = time.time()
    cfg = config or PipelineConfig()

    for k, v in kwargs.items():
        if k == "agent_profile" and v and not cfg.agent_profile:
            cfg.agent_profile = v if isinstance(v, dict) else None
            if isinstance(v, str):
                cfg.agent_profile_name = v
        elif k == "complexity" and not cfg.complexity:
            cfg.complexity = v
        elif not hasattr(cfg, k):
            setattr(cfg, k, v)

    task_complexity = get_task_complexity(task_text)
    task_types = detect_task_types(task_text)
    weights = get_dynamic_weights(task_text)

    pattern_warnings = []
    if cfg.enable_lessons:
        try:
            pattern_warnings = get_pattern_warnings(task_text)
        except Exception:
            pattern_warnings = []

    similar_decisions = []
    if cfg.enable_embedding:
        try:
            similar_decisions = find_similar_decisions(task_text, limit=3)
        except Exception:
            similar_decisions = []

    check_result = check10d_run(
        task_text,
        agent_profile=cfg.agent_profile,
    )

    confidences = assess_all_confidences(check_result.get("answers", {}))
    low_conf_dims = get_low_confidence_dimensions(confidences, threshold=cfg.confidence_threshold)

    # #10 分层判断
    try:
        layered_verdict = build_layered_verdict(task_text, check_result.get("answers", {}), confidences)
    except Exception:
        layered_verdict = None

    # #8 后悔预演
    try:
        core_stmt = ""
        if layered_verdict and layered_verdict.core:
            core_stmt = layered_verdict.core[0].statement
        hindsight_result = counterfactual_hindsight(
            decision=task_text,
            task_text=task_text,
            core_judgment=core_stmt,
        )
    except Exception:
        hindsight_result = None

    adversarial_data = None
    if cfg.enable_adversarial:
        try:
            objections = trace_call(
                "adversarial.generate_objections",
                lambda: generate_objections(task_text, check_result),
            )
            strong_unanswered = [o for o in objections if o.strength == "strong" and not o.response]
            robustness = max(0, 100 - len(strong_unanswered) * 20)
            verdict = "REJECT" if robustness < 40 else "MODIFY" if robustness < 70 else "PASS"
            adversarial_data = {
                "robustness": robustness,
                "verdict": verdict,
                "strong_objections": [
                    {"dimension": o.dimension_id, "text": o.objection_text}
                    for o in strong_unanswered
                ],
                "total_objections": len(objections),
            }
        except Exception:
            pass

    qiushi_data = None
    if cfg.enable_qiushi:
        try:
            qr = quick_qiushi_check(task_text)
            if qr:
                qiushi_data = {
                    "is_qiushi": qr.is_qiushi,
                    "verdict": qr.verdict,
                }
        except Exception:
            pass

    blind_spots_data = []
    if cfg.agent_profile_name:
        try:
            blind_spots = get_blind_spots(cfg.agent_profile_name)
            blind_spots_data = [
                {"dimension": b.dimension_id, "description": b.description, "frequency": b.frequency}
                for b in blind_spots[:5]
            ]
        except Exception:
            pass

    # #6 目标层次对齐检?
    goals_alignment = None
    if cfg.agent_profile:
        try:
            goals_alignment = check_goals_alignment(task_text, cfg.agent_profile)
        except Exception:
            goals_alignment = None

    elapsed = time.time() - start_time

    # Build scores from confidences (ConfidenceScore objects) or use fallback
    confidence_scores = {}
    for k, v in confidences.items():
        if hasattr(v, "score"):
            confidence_scores[k] = float(v.score)
        elif hasattr(v, "__float__"):
            confidence_scores[k] = float(v)
        else:
            confidence_scores[k] = v

    # Fallback: if no confidences (answers empty from check10d_run),
    # generate synthetic scores via keyword matching for demo purposes
    if not confidence_scores:
        DIM_KEYWORDS = {
            "d1_cognition": ["判断", "分析", "认知", "信息", "思考", "决策", "选择"],
            "d2_game_theory": ["对方", "博弈", "竞争", "合作", "利益", "利弊", "得失"],
            "d3_economics": ["成本", "收益", "经济", "划算", "值不值", "代价", "机会"],
            "d4_dialectics": ["矛盾", "对立", "辩证", "转化", "利弊", "优劣", "主次"],
            "d5_emotion": ["情绪", "感受", "焦虑", "担心", "害怕", "期待", "开心", "纠结"],
            "d6_intuition": ["直觉", "感觉", "第六感", "第一反应", "下意识"],
            "d7_morality": ["道德", "对错", "应该", "原则", "价值观", "责任", "良心"],
            "d8_social": ["别人", "他人", "社会", "群体", "关系", "看法", "评价"],
            "d9_time": ["长期", "短期", "未来", "以后", "时间", "耐心", "时机"],
            "d10_metacognition": ["反思", "思考方式", "认知", "自我", "觉察", "元认知"],
        }
        for dim_id in ["d1_cognition", "d2_game_theory", "d3_economics", "d4_dialectics", "d5_emotion", "d6_intuition", "d7_morality", "d8_social", "d9_time", "d10_metacognition"]:
            # Fallback: uniform moderate score when no LLM answers available
            confidence_scores[dim_id] = 0.5
    causal_result = None
    try:
        causal_result = build_causal_chain({"task": task_text, "scores": confidence_scores, "weights": weights, "dimensions": {d["id"]: d for d in check_result.get("dimensions", [])}})
    except Exception:
        pass

    # #1 递归触发探测
    probe_result = None
    try:
        probe_result = recursive_probe(task_text, confidence_scores, {d["id"]: d for d in check_result.get("dimensions", [])}, depth=0)
    except Exception:
        pass

    # #2 元认知自我审?
    meta_result = None
    try:
        meta_result = metacognitive_review({"scores": confidence_scores, "weights": weights}, task_text)
    except Exception:
        pass

    # #4 多agent辩论
    debate_result = None
    try:
        debate_result = run_debate(task_text, {"scores": confidence_scores, "dimensions": {d["id"]: d for d in check_result.get("dimensions", [])}})
    except Exception:
        pass

    return {
        "task": task_text,
        "complexity": task_complexity,
        "task_types": task_types,
        "weights": weights,
        "weighted_dims": [k for k, v in sorted(weights.items(), key=lambda x: -x[1]) if v > 0.15],
        "check_result": check_result,
        "confidences": {k: float(v) if hasattr(v, "__float__") else v for k, v in confidences.items()},
        "low_confidence_dims": low_conf_dims,
        "confidence_threshold": cfg.confidence_threshold,
        "layered_verdict": layered_verdict.to_dict() if layered_verdict else None,
        "hindsight": hindsight_result.to_dict() if hindsight_result else None,
        "adversarial": adversarial_data,
        "qiushi": qiushi_data,
        "similar_decisions": [
            {"task": s.get("task", ""), "decision": s.get("decision", ""), "score": float(s.get("score", 0))}
            for s in similar_decisions
        ],
        "pattern_warnings": [
            {"dimension": w.dimension, "description": w.description, "prevention": w.prevention_tip}
            for w in pattern_warnings
        ],
        "blind_spots": blind_spots_data,
        "goals_alignment": goals_alignment,
        "causal_chain": causal_result,
        "recursive_probes": probe_result,
        "meta_verdict": meta_result,
        "debate_result": debate_result,
        "needs_help": bool(low_conf_dims and any(d in low_conf_dims for d in ["game_theory", "emotional"])),
        "meta": {
            "pipeline_version": "3.1",
            "elapsed_ms": round(elapsed * 1000, 1),
        },
    }


def format_full_report(report: dict) -> str:
    lines = []
    lines.append("=" * 50)
    lines.append("  " + report["task"])
    lines.append("  复杂? " + report["complexity"] + "  |  类型: " + ", ".join(report["task_types"]))
    lines.append("=" * 50)

    lines.append("")
    lines.append("[动态权重]")
    for k, v in sorted(report["weights"].items(), key=lambda x: -x[1]):
        bar = "=" * int(v * 30)
        lines.append("  " + k + " " + bar + " " + str(round(v * 100)) + "%")

    if report.get("pattern_warnings"):
        lines.append("")
        lines.append("[教训警告]")
        for w in report["pattern_warnings"]:
            lines.append("  ! [" + w["dimension"] + "] " + w["description"])

    if report.get("similar_decisions"):
        lines.append("")
        lines.append("[相似决策]")
        for s in report["similar_decisions"]:
            lines.append("  -> " + s["task"] + " => " + s["decision"] + " (" + str(round(s["score"] * 100)) + "%)")

    if report.get("low_confidence_dims"):
        lines.append("")
        lines.append("[低置信度维度] " + ", ".join(report["low_confidence_dims"]))

    # #10 分层判断
    if report.get("layered_verdict"):
        lv = report["layered_verdict"]
        lines.append("")
        lines.append("[置信度分层]")
        lines.append(f"  整体置信? {lv.get('overall_confidence', 0):.0%}")
        lines.append(f"  {lv.get('summary', '')}")
        if lv.get("core"):
            lines.append(f"  🟢 核心判断({len(lv['core'])}?可闭眼跟):")
            for c in lv["core"][:3]:
                lines.append(f"    ?{c.get('statement', '')[:80]}")
        if lv.get("conditionals"):
            lines.append(f"  🟡 条件判断({len(lv['conditionals'])}?:")
            for c in lv["conditionals"][:2]:
                lines.append(f"    ? {c.get('if', '')} ?{c.get('then', '')[:60]}")
        if lv.get("blind_spots"):
            lines.append(f"  🔴 盲区警告({len(lv['blind_spots'])}?:")
            for b in lv["blind_spots"][:3]:
                lines.append(f"    ?{b.get('area', '')}: {b.get('warning', '')}")

    # #8 后悔预演
    if report.get("hindsight"):
        hs = report["hindsight"]
        lines.append("")
        lines.append("[🔮 后悔预演]")
        insight = hs.get("insight", "")
        lines.append(f"  💡 {insight}")
        proceed = hs.get("should_proceed", False)
        lines.append(f"  {'?可推进，注意风控' if proceed else '?暂缓，设置冷静期'}")

    if report.get("adversarial"):
        adv = report["adversarial"]
        lines.append("")
        lines.append("[对抗性验证] 稳健? " + str(adv["robustness"]) + "%  |  " + adv["verdict"])
        for obj in adv.get("strong_objections", []):
            lines.append("  x [" + obj["dimension"] + "] " + obj["text"])

    if report.get("qiushi") and not report["qiushi"].get("is_qiushi", True):
        lines.append("")
        lines.append("[求是警告] " + report["qiushi"].get("verdict", ""))

    if report.get("blind_spots"):
        lines.append("")
        lines.append("[Profile盲区]")
        for b in report["blind_spots"]:
            lines.append("  ? [" + b["dimension"] + "] " + b["description"])

    # #6 目标层次对齐
    # #3 因果?
    if report.get("causal_chain"):
        cc = report["causal_chain"]
        lines.append("")
        lines.append("[因果链]")
        lines.append("  " + cc.get("summary", ""))
        if cc.get("root_causes"):
            lines.append("  根因: " + ", ".join(cc.get("root_causes", [])[:3]))
        for c in cc.get("chain", [])[:5]:
            bar = "#" * int(c.get("impact_pct", 0) * 20)
            lines.append("  %-12s %5.0f%% %s" % (c.get("dimension_name", "")[:12], c.get("score", 0) * 100, bar))

    # #1 递归触发
    if report.get("recursive_probes"):
        rp = report["recursive_probes"]
        lines.append("")
        lines.append("[递归探测] 深度=%d | 追问=%d" % (rp.get("depth_reached", 0), rp.get("total_probes", 0)))
        for p in rp.get("probes", [])[:4]:
            icon = "🔍" if p.get("trigger_reason") == "low" else "⚡"
            lines.append("  %s %s (%.0f%%)" % (icon, p.get("dimension_name", ""), p.get("score", 0) * 100))
            for q in p.get("questions", [])[:2]:
                lines.append("    ❓ %s" % q)

    # #2 元认知审查
    if report.get("meta_verdict"):
        mv = report["meta_verdict"]
        verdict_icon = {"PROCEED": "✅", "REVIEW": "👀", "HOLD": "🛑"}.get(mv.get("meta_verdict", ""), "❔")
        lines.append("")
        lines.append("[元认知审查] %s (调整: %+.0f%%)" % (verdict_icon, (mv.get("confidence_adjustment", 0) or 0) * 100))
        for f in mv.get("flags", [])[:3]:
            lines.append("  ! [%s] %s" % (f.get("type", ""), f.get("description", "")[:60]))

    # #4 多agent辩论
    if report.get("debate_result"):
        dr = report["debate_result"]
        lines.append("")
        lines.append("[多Agent辩论] %s vs %s" % (
            dr.get("support_args", []) and "正方" or "",
            dr.get("object_args", []) and "反方" or ""))
        for a in dr.get("arguments", [])[:5]:
            icon = a.get("icon", "?")
            strength = "*" if a.get("strength") == "strong" else " "
            lines.append("  %s%s %s" % (strength, icon, a.get("text", "")[:70]))

    if report.get("goals_alignment"):
        ga = report["goals_alignment"]
        lines.append("")
        lines.append("[目标层次对齐]")
        verdict_icon = {"SERVES_GOALS": "✅", "NEUTRAL": "➖", "DETRACTS_FROM_GOALS": "❌"}
        icon = verdict_icon.get(ga.get("verdict", "NEUTRAL"), "❔")
        lines.append(f"  {icon} {ga.get('verdict_reason', '')}")
        if ga.get("has_archetype") and ga.get("archetype"):
            arch = ga["archetype"]
            lines.append(f"  原型: {arch['name']} | {arch['典型提问']}")
        for g in ga.get("goals_alignment", [])[:3]:
            g_icon = "✅" if g["aligned"] else ("❔" if g["aligned"] is None else "❌")
            lines.append(f"  {g_icon} {g['goal']} [{g['timeframe']}] ({g['score']:.0%})")
        if ga.get("overall_alignment", 0) > 0:
            lines.append(f"  整体对齐: {ga['overall_alignment']:.0%}")

    lines.append("")
    lines.append("=" * 50)
    lines.append("耗时: " + str(report["meta"]["elapsed_ms"]) + "ms")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# 机器可读 JSON 输出格式（聚活项目设计）
# 输出给 Agent 调用，不是给人读
# ─────────────────────────────────────────────────────────────────

def format_guyong_json(report: dict) -> dict:
    """
    返回机器可解析的 JSON 兼容 dict?

    参考格式：
    {
        "task": "...",
        "complexity": "high",
        "dimensions_used": ["博弈?, "情绪智能", "时间折扣"],
        "dimensions": {
            "game_theory": {"score": 0.8, "confidence": 0.75, "weight": 0.2},
            "emotional": {"score": 0.6, "confidence": 0.45, "weight": 0.15},
        },
        "confidence": 0.7,
        "needs_help": true,
        "reason": "情绪信号过强，置信度不足"
    }

    建议：confidence < 0.5 ?needs_help=true 时，Agent 应请求人工确认?
    """
    task = report.get("task", "")
    complexity = report.get("complexity", "auto")
    weights = report.get("weights", {})
    confidences = report.get("confidences", {})
    check_result = report.get("check_result", {})
    must_check = check_result.get("must_check", [])
    important = check_result.get("important", [])
    skipped = check_result.get("skipped", [])
    layered = report.get("layered_verdict") or {}

    # 维度名称映射
    DIM_NAME = {
        "cognitive": "认知",
        "game_theory": "博弈",
        "economic": "经济",
        "dialectical": "辩证",
        "emotional": "情绪智能",
        "intuitive": "直觉",
        "moral": "道德",
        "social": "社会",
        "temporal": "时间折扣",
        "metacognitive": "元认知",
    }

    # 构建每维度详情
    dims_used_ids = must_check + important
    dims_detail = {}
    for dim_id in dims_used_ids:
        raw_score = confidences.get(dim_id, 0.5)
        score = float(raw_score.score if hasattr(raw_score, "score") else raw_score) if raw_score else 0.5
        conf = float(raw_score.confidence if hasattr(raw_score, "confidence") else score)
        dims_detail[dim_id] = {
            "name": DIM_NAME.get(dim_id, dim_id),
            "score": round(score, 2),
            "confidence": round(conf, 2),
            "weight": round(weights.get(dim_id, 0.0), 3),
            "priority": "must" if dim_id in must_check else "important",
        }

    # 整体 confidence = 加权平均
    if dims_detail:
        total_weight = sum(v["confidence"] * v["weight"] for v in dims_detail.values() if v["weight"] > 0)
        weight_sum = sum(v["weight"] for v in dims_detail.values() if v["weight"] > 0)
        overall_conf = total_weight / weight_sum if weight_sum > 0 else 0.5
    else:
        overall_conf = layered.get("overall_confidence", 0.5)

    # needs_help 判断（聚活项目设计）：
    # - game_theory emotional 任一 confidence < 0.5 → needs_help=True
    # - 整体 confidence < 0.4 → needs_help=True
    critical_dims_low = [
        dim_id for dim_id in ["game_theory", "emotional"]
        if dim_id in dims_detail and dims_detail[dim_id]["confidence"] < 0.5
    ]
    needs_help = bool(critical_dims_low or overall_conf < 0.4)

    # reason
    if critical_dims_low:
        reason = "以下关键维度置信度不? " + ", ".join(
            DIM_NAME.get(d, d) for d in critical_dims_low
        )
    elif overall_conf < 0.4:
        reason = "整体置信度过低（{:.0%}），信息不足".format(overall_conf)
    else:
        reason = None

    # 参与判断的维度名称列?
    dims_used_names = [DIM_NAME.get(d, d) for d in dims_used_ids]

    return {
        "task": task,
        "complexity": complexity,
        "dimensions_used": dims_used_names,
        "dimensions": dims_detail,
        "confidence": round(overall_conf, 2),
        "needs_help": needs_help,
        "reason": reason,
        # 额外字段（供参考）
        "verdict": layered.get("summary", None),
        "low_confidence_dims": report.get("low_confidence_dims", []),
        "weighted_dims": report.get("weighted_dims", []),
        "elapsed_ms": report.get("meta", {}).get("elapsed_ms", 0),
    }
