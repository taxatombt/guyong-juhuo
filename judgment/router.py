import time
"""
router.py — 十维判断框架核心路由

接口：
- check10d(task_text, agent_profile=None, complexity="auto") -> dict
  标准化结构化输出，机器可解析

- check10d_run(task_text, agent_profile=None) -> dict
  并行检视接口：asyncio 并行执行10维度分析（critical模式专用）

- check10d_full(task_text, config) -> dict
  完整Pipeline：权重+十维+置信度+对抗+求是+Embedding+教训

- format_report(result) -> str
  旧兼容，人可读

- format_structured(result) -> str
  新，人可读
"""

import re
import asyncio
from datetime import datetime
try:
    from paths import PATHS
except ImportError:
    import os
    PATHS = {"DATA": os.path.join(os.path.dirname(__file__), "..", "data")}
from judgment.dimensions import DIMENSIONS
from correlation_memory import recall_correlation_history as recall_causal_history, inject_to_judgment_input, find_similar_events, init
from judgment.closed_loop import start_verdict_listener
from judgment.self_evolver import start_evolver_scheduler

# Verdict 自动积累
from evolver.verdict_collector import save_verdict as _save_auto_verdict, VerdictRecord

# 因果链教训层
from judgment.lessons import (
    lessons_to_prompt,
    classify_task_domain,
    extract_and_save_from_case,
)

# MiniMind 长上下文压缩（Compactor v1）
from judgment.compactor import compact_history

# LLM 调用函数（从 router.py 拆分，独立可测）
# 注意：inject_emotion_signal 需使用 router.py 中的 global_emotion_system，
# 已在 router.py line 108 初始化，此处直接用同名引用。
from judgment.llm_calls import (
    inject_emotion_signal,
    _build_answer_prompt,
    _answer_questions,
    _keyword_match,
    _synthesize_verdict,
    MUST_CHECK,
    predict_user_choice,
    _verify_judgment,
    _score_verdict_candidate,
)

# P1 IntentRouter：ZeusHammer LocalBrain 启发，80%% 任务不需要LLM
from judgment.intent_router import should_skip_judgment, route_input, IntentType

from judgment.pipeline import run_pipeline, JudgmentContext

# ShortTermCache L1：会话内缓存，减少重复LLM调用
from judgment.short_term_cache import short_term_cache, inject_short_term_context

# router_utils: 独立工公函数（从 router.py 提取）
# _keyword_match: route() | _judge_complexity: check10d()
# format_report/format_structured: 公共 API re-export
from judgment.router_utils import (
    _keyword_match,
    _judge_complexity,
    format_report,
    format_structured,
)

# LLM 编排层（从 router.py 提取）
from judgment.llm_orchestrator import (
    _inject_profile_questions,
    inject_profile_into_dimensions,
)


# P1 IntentRouter 快速响应（fast path，避免完整LLM调用）
def _quick_status_response(task_text: str) -> dict:
    """STATUS_QUERY intent → 简短状态查询"""
    return {
        "verdict": "状态查询",
        "confidence": 0.95,
        "intent_type": "STATUS_QUERY",
        "summary": f"当前状态正常",
        "dimensions": {},
    }


def _quick_answer_response(task_text: str) -> dict:
    """SHORT_ANSWER intent → 一句话回答"""
    return {
        "verdict": "简短回答",
        "confidence": 0.9,
        "intent_type": "SHORT_ANSWER",
        "summary": f"回答：{task_text[:50]}",
        "dimensions": {},
    }


def _quick_confirm_response(task_text: str) -> dict:
    """CONFIRM intent → 确认类查询"""
    return {
        "verdict": "确认请求",
        "confidence": 0.95,
        "intent_type": "CONFIRM",
        "summary": f"确认收到",
        "dimensions": {},
    }


# MiniMind 长上下文压缩：超长 prompt 时自动摘要
# 调用位置：check10d 和 check10d_run 中，_answer_questions 调用之前
_COMPACT_THRESHOLD = 6000  # token 阈值，超过则压缩

def _maybe_compact_ctx(profile_entries: list, lessons_ctx: str,
                       history_context: str = "") -> tuple:
    """
    如果 profile_entries + lessons_ctx + history_context 合计超过阈值，
    用 compact_history() 压缩上下文。

    Returns:
        (compact_profile_entries, compact_lessons_ctx, compact_history_context, was_compacted)
    """
    # 估算 token 数（char * 0.25）
    def _tok(s):
        return len(str(s)) * 0.25

    total = _tok(profile_entries) + _tok(lessons_ctx) + _tok(history_context)
    if total < _COMPACT_THRESHOLD:
        return profile_entries, lessons_ctx, history_context, False

    # 构建压缩消息列表
    items = []
    # profile_entries: 列表[dict] -> 转文本摘要
    if profile_entries:
        count = len(profile_entries)
        summary_text = f"[背景摘要] 共 {count} 条用户背景信息。核心："
        for e in profile_entries[:5]:  # 只取前5条
            if isinstance(e, dict):
                claim = e.get('claim', e.get('content', str(e)))
                summary_text += claim[:30] + "；"
            else:
                summary_text += str(e)[:30] + "；"
        if count > 5:
            summary_text += f"等（共{count}条）"
        items.append({'role': 'system', 'content': summary_text})

    # lessons_ctx: 字符串 -> system 消息
    if lessons_ctx:
        items.append({'role': 'system', 'content': f"[教训摘要] {lessons_ctx}"})

    # history_context: 字符串 -> system 消息
    if history_context:
        items.append({'role': 'system', 'content': f"[历史摘要] {history_context}"})

    result = compact_history(items, reason="long_context_auto")
    # compact_history 返回 CompactionResult.compacted_items / .summary
    summary = result.summary if result.summary else ""
    return [], summary, "", True  # 原始 entries 压缩为 summary

# 懒启动标记（避免 import 时执行副作用，测试可正常 mock）
_STARTED = False

def _ensure_started():
    """首次调用 check10d_run 时才启动，重复调用无操作。"""
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    init()
    start_verdict_listener()
    start_evolver_scheduler()
    _init_exp()  # 初始化经历表
    # [ZeusHammer EventBus] 事件总线初始化
    from judgment.event_bus import setup_event_bus
    setup_event_bus()

# 兼容旧接口命名
class _CausalMemoryCompat:
    """兼容层：让 correlation_memory 作为可调用对象访问模块级函数"""
    def recall_causal_history(self, task, max_events=3):
        return recall_causal_history(task, max_events)
    def inject_to_judgment_input(self, task):
        return inject_to_judgment_input(task)

correlation_memory = _CausalMemoryCompat()
from self_model.self_model import get_self_warnings
from curiosity.curiosity_engine import CuriosityEngine, trigger_from_low_confidence
from emotion_system.emotion_system import EmotionSystem

# Emotion × Judgment 集成：PAD状态调制维度权重
from subsystems.judgment.emotion_adapter import get_emotion_modulation

# 新增：自我复盘 + Fitness Baseline
from .self_review import SelfReviewSystem
from .closed_loop import record_judgment, snapshot_judgment, get_prior_adjustments, _get_db_conn
from .fitness_baseline import FitnessBaseline

# LLM接入：MiniMax适配器
from llm_adapter.minimax import get_adapter
from llm_adapter.base import CompletionRequest

# 经历层：历史判断记忆
from judgment.experiences import get_context_for_judgment, save_experience, record_outcome as _rec_outcome_exp, init as _init_exp
from judgment.behavior_logger import log_agent_behavior, ActionChannel

# 途径1：生平事实层
from judgment.biography import get_context as get_bio_context, extract_from_text as extract_bio, log_batch as log_bio_batch
from judgment.pets import update_from_emotion, pet_to_prompt, get_status_summary, interact as _pet_interact, get_pet as _get_pet

# P0改进：因果推断引擎 - 给judgment提供推理底座
from correlation_memory.correlation_inference import CorrelationInferenceEngine, infer_correlation_chain as infer_causal_chain

# P3改进：十维推理规则引擎
from .judgment_rules import rule_based_precheck, get_rule_scores

# Stop Hook：事件捕获
from .stop_hook import capture_judgment, capture_verdict, finalize_session

# Hermes启发：上下文围栏 + 生命周期钩子
from .context_fence import build_judgment_context, scan_threats
from .life_cycle_hooks import prefetch_all, get_lifecycle_hooks

# P1改进：验证层
from .verifier import JudgmentVerifier
_verifier = None

def _get_verifier():
    global _verifier
    if _verifier is None:
        _verifier = JudgmentVerifier()
    return _verifier

global_emotion_system = EmotionSystem()
global_self_review = None  # 懒加载

def _get_self_review():
    global global_self_review
    if global_self_review is None:
        global_self_review = SelfReviewSystem()
    return global_self_review

def route(text):
    """旧接口，保持兼容"""
    for path in PATHS:
        if _keyword_match(text, path.trigger):
            dims = [d for d in DIMENSIONS if d.id in path.methods]
            return {
                "matched": True,
                "path": path.to_dict(),
                "dimensions": [d.to_dict() for d in dims],
                "sample_text": text,
            }
    return {"matched": False, "sample_text": text}


def check10d(task_text, agent_profile=None, complexity="auto", emotion_state=None, user_id: str = "default"):
    """
    标准化接口：十维检视
    因果记忆：自动注入相关历史判断到任务上下文
    情绪调制：PAD状态直接调制维度权重和信心度
    经历层：历史判断自动作为参考上下文

    参数:
        task_text: 任务描述
        agent_profile: 可选dict {
            "name": "<persona>",           # 模拟对象
            "values": ["成就", "自由"],  # 价值排序
            "biases": ["过度分析"],      # 已知偏差
            "style": "理性优先"          # 思考风格
        }
        complexity: "auto" | "simple" | "complex" | "critical"
        emotion_state: 可选dict {
            "P": float,   # 愉悦度 -1~+1
            "A": float,   # 激活度 -1~+1
            "D": float,   # 支配度 -1~+1
        }

    返回:
        dict，包含 verdict / confidence / 各维度分析 / 历史参考
    """
    # 懒启动（初始化 experiences 表等）
    _ensure_started()

    # ── P1 IntentRouter：ZeusHammer LocalBrain ─────────────────────
    # 在进入昂贵LLM调用前，先判断意图类型
    intent_type = route_input(task_text)
    if intent_type == IntentType.STATUS_QUERY:
        return _quick_status_response(task_text)
    elif intent_type == IntentType.SHORT_ANSWER:
        return _quick_answer_response(task_text)
    elif intent_type == IntentType.CONFIRM:
        return _quick_confirm_response(task_text)

    # ── L1 ShortTermCache：先查会话内缓存，减少重复LLM调用 ───────
    # ZeusHammer 三层记忆 L1，会话内跨任务共享上下文
    stc_context = inject_short_term_context(task_text, top_k=3)
    if stc_context:
        # 缓存命中：简短任务可考虑直接复用
        # 目前记录到 ctx，后续可优化"缓存命中→跳过LLM"逻辑
        ctx._profile_entries.append({
            "priority": 5,  # 最高优先级
            "source": "session_cache",
            "recency": 1.0,
            "claim": stc_context,
            "contradiction_flag": False,
        })

    # ── P0-3 Pipeline 编排（链式注入）──────────────────────────────
    # 每个注入器独立函数，顺序执行，结果写入 ctx
    ctx = JudgmentContext(
        task_text=task_text,
        original_task=task_text,
        agent_profile=agent_profile,
        complexity=complexity,
        emotion_state=emotion_state,
        user_id=user_id,
    )
    ctx = run_pipeline(ctx)
    
    # Pipeline 输出回写局部变量（兼容后续逻辑）
    # 注意：不再用 merge_prompt_context() 拼接文本
    # 三路数据统一通过 inject_unified_profile → _profile_entries → _answer_questions
    task_text = ctx.task_text                   # 原始任务，不含拼接上下文
    emotion_modulation = ctx.emotion_modulation
    emotion_detection = ctx.emotion_detection
    causal_result = ctx.causal_result

    # 宠物系统：主人情绪变化 → 宠物状态同步更新
    if emotion_detection and emotion_detection.emotion_label:
        pet_result = update_from_emotion(
            pet_id=user_id,
            emotion_label=emotion_detection.emotion_label,
            owner_pad={"P": emotion_detection.p_score, "A": emotion_detection.a_score, "D": emotion_detection.d_score} if hasattr(emotion_detection, "p_score") else None
        )
        # 宠物心情变化附加到判断上下文中
        if pet_result and pet_result.get("reaction"):
            ctx._pet_reaction = pet_result["reaction"]

    # Hook 上下文（Hermes 启发）
    hook_context = {}
    fenced_context = ""
    
    # P3改进：规则预检 - 先用规则快速判断，降低LLM调用
    rule_precheck = rule_based_precheck(ctx.original_task)
    rule_scores = rule_precheck["rule_scores"]
    
    if complexity == "auto":
        complexity = _judge_complexity(task_text)

    if complexity == "simple":
        # 极简：只跑最核心的博弈论+情绪（人类高频踩坑维度）
        must = ["game_theory", "emotional"]
        important = []
        skipped = [d.id for d in DIMENSIONS
                   if d.id not in must]
    elif complexity == "complex":
        must = MUST_CHECK + ["emotional", "temporal"]
        important = ["intuitive", "moral"]
        skipped = []  # metacognitive 由 post-hoc 标准差计算，不需要跳过
    elif complexity == "critical":
        must = [d.id for d in DIMENSIONS]
        important = []
        skipped = []
    else:
        must = MUST_CHECK
        important = IMPORTANT
        skipped = NICE_TO_HAVE

    questions = {}
    for dim in DIMENSIONS:
        questions[dim.id] = dim.questions[:]

    # 核心问题1修复：biography → 每个维度个性化追问
    if agent_profile:
        _, dim_prompts = inject_profile_into_dimensions(agent_profile, task_text)
        # 兼容旧 cognitive 追加
        extra = _inject_profile_questions(agent_profile, task_text)
        if extra:
            questions["cognitive"].extend(extra)
        # 新：每个维度个性化追问
        for dim_id, extra_prompts in dim_prompts.items():
            if dim_id in questions:
                questions[dim_id].extend(extra_prompts)
        # 维度权重注入到 prior_adjustments
        weights, _ = inject_profile_into_dimensions(agent_profile, task_text)
        for dim_id, w in weights.items():
            ctx.prior_adjustments[dim_id] = ctx.prior_adjustments.get(dim_id, 1.0) * w

    checked = len([d.id for d in DIMENSIONS if d.id not in skipped])

    # 自我模型：获取自我提醒
    self_warnings, self_strengths = get_self_warnings({
        "skipped": skipped,
        "must_check": must,
        "important": important,
    })

    # 好奇心引擎：低置信度自动触发缺口收集
    from .confidence import calculate_average_confidence
    avg_confidence = 0.5
    dim_confidence = {}
    if 'dim_confidence' in locals():
        avg_confidence = calculate_average_confidence(dim_confidence)
    
    curiosity_item = None
    if avg_confidence < 0.5 and avg_confidence > 0:
        from ..curiosity.curiosity_engine import trigger_from_low_confidence
        curiosity_item = trigger_from_low_confidence({
            "original_task": ctx.original_task,
            "average_confidence": avg_confidence,
            "dim_confidence": dim_confidence if 'dim_confidence' in locals() else {},
        }, current_task=ctx.original_task[:60])

    # 情绪检测已在 pipeline.inject_emotion() 中完成（fallback 也已处理）

    # LLM接入：MiniMax回答所有维度问题
    prior_adj = ctx.prior_adjustments
    # P0 FIX: ctx.unified_context 已在 merge_prompt_context() 里（inject_user_model 生成）
    # 不再单独传 history_context / bio_context（避免重复注入 prompt）
    # UnifiedProfile entries：ctx._profile_entries 由 inject_user_model 填充
    _profile_entries = getattr(ctx, '_profile_entries', None) or []
    # 因果链教训注入（从同类判断结果中提取的具体教训）
    _task_domain = classify_task_domain(ctx.task_text)
    _lessons_ctx = lessons_to_prompt(domain=_task_domain)
    # [MiniMind Compactor] 长上下文自动压缩
    _profile_entries, _lessons_ctx, _hist_ctx, _was_compact = _maybe_compact_ctx(
        _profile_entries, _lessons_ctx, ctx.history_context or ""
    )
    # L3 感知层汇聚（web/scraping/rss/email/experiences 外部信号）
    try:
        from perception.summary import get_perception_summary
        _ps = get_perception_summary(task_topic=ctx.task_text, limit=10)
        _perception_ctx = _ps.to_prompt() if _ps else ""
    except Exception:
        _perception_ctx = ""

    # [Hermes Orange-Book] Honcho 软画像注入（P1: decision_style结构化影响）
    _decision_style = ""
    try:
        from judgment.honcho_soft_profile import infer_soft_profile, soft_profile_to_prompt
        _soft_profile = infer_soft_profile(user_id)
        _decision_style = _soft_profile.get("decision_style", "") or ""
        _soft_ctx = soft_profile_to_prompt(user_id) or ""
        if _soft_ctx:
            _perception_ctx = (_soft_ctx + chr(10) + _perception_ctx).strip()
    except Exception:
        pass

    answers = _answer_questions(
        ctx.merge_prompt_context(),  # unified_context 优先 + 三路已合并
        questions,
        agent_profile,
        prior_adj,
        _hist_ctx,  # 压缩后的历史摘要
        "",  # 不再单独传 bio_context（已合并到 unified_context）
        _profile_entries,  # UnifiedProfile.to_prompt() 标注注入
        _lessons_ctx,      # 历史教训注入（因果链教训，被压缩时为摘要）
        _perception_ctx,   # L3 感知层外部信号
        pet_to_prompt(user_id),  # 宠物状态注入
        _decision_style,    # P1: DecisionStyle结构化影响
    )

    # ── Metacognitive：9维置信度标准差 → 元监控 ────────────────────
    # Review #3: metacognitive 不是第10个独立维度，而是对前9维的元监控
    _non_mc_dims = [d.id for d in DIMENSIONS if d.id != "metacognitive"]
    _dim_scores = []
    for _dim in _non_mc_dims:
        _ans_text = answers.get(_dim, "") or ""
        if _ans_text:
            _s = _score_verdict_candidate(_ans_text)
            if _s > 0:
                _dim_scores.append(_s)

    if len(_dim_scores) >= 2:
        import statistics
        _std = statistics.stdev(_dim_scores)
        _mean = statistics.mean(_dim_scores)
        # 标准差大 → 维度间判断不一致 → metacognitive 警告
        # 标准差小 → 维度一致 → metacognitive 稳定
        _mc_confidence = max(0.1, 1.0 - (_std * 2.5))  # 方差越大，置信度越低
        _instability = _std > 0.15
        _mc_reasoning = (
            f"9维判断标准差={_std:.3f}，均值={_mean:.3f}。"
            f"{'【告警】各维度判断不一致，判断不稳定，建议重新审视核心假设。' if _instability else '各维度判断基本一致，判断稳定。'}"
        )
    else:
        _mc_confidence = 0.5
        _mc_reasoning = "维度答案不足，无法计算元监控置信度。"

    answers["metacognitive"] = _mc_reasoning

    _ret = {
        "task": ctx.task_text,
        "original_task": ctx.original_task,
        "complexity": complexity,
        "must_check": must,
        "important": important,
        "skipped": skipped,
        # Pipeline 上下文（供 check10d_run 等下游使用）
        "history_context": ctx.history_context,
        "bio_context": ctx.bio_context,
        "causal_context": ctx.causal_context,
        "questions": questions,
        "answers": answers,
        "agent_profile": agent_profile,
        # causal_result 可能为空字典（run_pipeline 未填充 → 用 .get() 兜底）
        "correlation_memory": (causal_result if isinstance(causal_result, dict) else {}) and {
            "has_history": (causal_result.get("summary") if isinstance(causal_result, dict) else None) is not None,
            "similar_events": (causal_result.get("similar_events") if isinstance(causal_result, dict) else None) or [],
            "causal_chains": (causal_result.get("causal_chains") if isinstance(causal_result, dict) else None) or [],
            "summary": (causal_result.get("summary") if isinstance(causal_result, dict) else "") or "",
            "causal_inference": (causal_result.get("causal_inference") if isinstance(causal_result, dict) else None),
        },
        # P3改进：规则预检结果
        "rule_precheck": {
            "needs_llm": rule_precheck["needs_llm"],
            "llm_dimensions": rule_precheck["llm_dimensions"],
            "low_score_dimensions": rule_precheck["low_score_dimensions"],
            "all_passed": rule_precheck["all_passed"],
        },
        # Hermes启发：上下文围栏
        "fenced_context": fenced_context,
        # Hermes启发：Hook召回的上下文
        "hook_context": {
            "correlation_memory": hook_context.get("correlation_memory"),
            "fitness": hook_context.get("fitness"),
            "instinct": hook_context.get("instinct"),
            "low_confidence_dims": hook_context.get("low_confidence_dims"),
        },
        "self_model": {
            "warnings": self_warnings,
            "strengths": self_strengths,
        },
        "curiosity": {
            "has_gap": curiosity_item is not None,
            "item_id": curiosity_item.id if curiosity_item else None,
        },
        "emotion": {
            "detected_emotions": [emotion_detection.emotion_label] if emotion_detection and emotion_detection.emotion_label else [],
            "need_attention": emotion_detection.is_signal if emotion_detection else False,
            "signal_type": emotion_detection.emotion_label if emotion_detection else None,
            "signal_description": emotion_detection.description if emotion_detection else "",
            # Emotion × Judgment 集成：PAD调制信息
            "pad_modulation": {
                "emotion_label": emotion_modulation.emotion_label if emotion_modulation else None,
                "intensity": emotion_modulation.intensity if emotion_modulation else 0.0,
                "dim_mods": emotion_modulation.dim_mods if emotion_modulation else {},
                "prompt_hint": emotion_modulation.prompt_hint if emotion_modulation else "",
                "confidence_adjustment": emotion_modulation.confidence_adjustment if emotion_modulation else 0.0,
                "recommended_dims": emotion_modulation.recommended_dims if emotion_modulation else [],
                "suppressed_dims": emotion_modulation.suppressed_dims if emotion_modulation else [],
            } if emotion_modulation else None,
        },
        "meta": {
            "total_dims": 10,
            "checked": checked,
            "skipped_count": len(skipped),
            "prior_adjustments": prior_adj,
            "decision_style": _decision_style,  # P1: Honcho软画像结构化影响
        }
    }

    # ── 闭环：记录因果链 ──────────────────────────────────────────────
    try:
        _dims_chosen = [d.id for d in DIMENSIONS if d.id not in skipped]
        _weights = {d: prior_adj.get(d, 1.0) for d in _dims_chosen}
        _chain_id = record_judgment(
            task_text=ctx.original_task[:300],
            dimensions=_dims_chosen,
            weights=_weights,
            reasoning={},
            user_id=user_id,
        )
        _ret["meta"]["chain_id"] = _chain_id
        
        # ── Verdict 自动积累：每次judgment自动记录 ──────────────────
        # source="auto" 表示系统自动记录，待用户反馈 verdict
        _auto_record = VerdictRecord(
            chain_id=_chain_id,
            task_text=ctx.original_task[:300],
            timestamp=datetime.now().isoformat(),
            verdict="pending",  # 待用户反馈
            source="auto",
            metadata={
                "complexity": complexity,
                "dimensions": _dims_chosen,
                "weights": _weights,
                "emotion": emotion_detection.emotion_label if emotion_detection and emotion_detection.emotion_label else None,
            }
        )
        _save_auto_verdict(_auto_record)
        
        # Stop Hook: 捕获judgment行为
        capture_judgment(
            task=ctx.original_task,
            dimensions=_dims_chosen,
            result={"decision": _ret.get("decision"), "scores": _ret.get("scores")},
            rule_precheck=rule_precheck
        )
        
        # P1改进：验证层 - 自我反驳（critical模式自动验证）
        if complexity == "critical":
            verifier = _get_verifier()
            verification = verifier.verify(_ret)
            _ret["meta"]["verification"] = verification
            
            # P0改进：因果推断 - 给判断提供推理底座
            inference_engine = CorrelationInferenceEngine()
            causal_infer = inference_engine.infer(
                situation=ctx.original_task,
                judgment_dimensions=must + important
            )
            _ret["correlation_memory"]["causal_inference"] = {
                "best_explanation": causal_infer.best_explanation,
                "reasoning_chain": causal_infer.reasoning_chain,
                "confidence": causal_infer.confidence,
                "needs_more_data": causal_infer.needs_more_data,
                "hypotheses_count": len(causal_infer.hypotheses)
            }
    except Exception:
        pass

    # ── Verdict 合成：从维度答案生成最终判断 ─────────────────────────
    verdict_str, confidence = _synthesize_verdict(ctx.original_task, _ret.get("answers", {}))
    _ret["verdict"] = verdict_str
    _ret["confidence"] = confidence

    # 经历层：存为历史记忆
    _chain_id = _ret.get("meta", {}).get("chain_id", "")
    try:
        save_experience(ctx.original_task, verdict_str, confidence, context=ctx.history_context, user_id=user_id, chain_id=_chain_id)
        # 途径3：行为日志（judgment 通道，无工具调用）
        log_agent_behavior(
            task_text=ctx.original_task,
            channel=ActionChannel.JUDGMENT,
            verdict=verdict_str,
            confidence=confidence,
            chain_id=_ret.get("meta", {}).get("chain_id", ""),
            tool_calls=[],  # router.py 仅做判断，无工具调用
            execution_result="",
            user_id=user_id,
        )
    except Exception:
        pass

    # Emotion × Judgment 集成：情绪调制信心度
    if emotion_modulation is not None and emotion_modulation.confidence_adjustment != 0.0:
        _old_conf = confidence
        _ret["confidence"] = max(0.0, min(1.0, confidence + emotion_modulation.confidence_adjustment))
        _ret["meta"]["emotion_confidence_adjustment"] = {
            "from": _old_conf,
            "adjustment": emotion_modulation.confidence_adjustment,
            "to": _ret["confidence"],
        }

    # UnifiedProfile entries 透传给外部（供 check10d_run / API 使用）
    _ret["_profile_entries"] = _profile_entries

    # 宠物状态（附加到结果中）
    _ret["pet"] = {
        "status": get_status_summary(user_id),
        "reaction": getattr(ctx, "_pet_reaction", None),
    }

    # [Hermes Orange-Book] Progressive Disclosure 渐进揭示
    try:
        from judgment.progressive_disclosure import apply_disclosure
        _dr = apply_disclosure(
            ctx.original_task,
            _ret.get("answers", {}),
            verdict_str,
            confidence,
            _ret,
        )
        _ret["disclosure"] = {
            "layer": _dr.layer,
            "needs_confirm": _dr.needs_user_confirm,
            "user_prompt": _dr.user_prompt,
            "suggestions": _dr.suggestions,
            "reveal_dimensions": _dr.reveal_dimensions,
        }
        _ret["meta"]["disclosure_layer"] = _dr.layer
    except Exception:
        pass

    return _ret


async def _analyze_dim(dim, task_text, agent_profile, dim_prompts: dict = None):
    """分析单个维度（asyncio协程）。所有维度同时执行，互不阻塞。"""
    await asyncio.sleep(0)  # 让出控制，允许其他协程并发执行
    return _analyze_dim_sync(dim, task_text, agent_profile, dim_prompts)


def _analyze_dim_sync(dim, task_text, agent_profile, dim_prompts: dict = None):
    """
    分析单个维度（同步版）。与 asyncio 版逻辑相同。

    核心问题1修复：biography → 每个维度的个性化追问，不只是 cognitive。
    dim_prompts: {dim_id: [追加追问列表]}，由 inject_profile_into_dimensions 生成。
    """
    questions = dim.questions[:]
    # 兼容旧接口：cognitive 维度的追加
    if agent_profile:
        extra = _inject_profile_questions(agent_profile, task_text)
        if extra:
            questions = questions + extra
    # 新：每个维度都有个性化追问
    if dim_prompts and dim.id in dim_prompts:
        questions = questions + dim_prompts[dim.id]
    return {dim.id: questions}


def check10d_run(task_text, agent_profile=None, emotion_state=None, user_id: str = "default", complexity: str = "critical"):
    """
    同步检视接口：直接调用 check10d。
    
    P1 Fix: simple 模式下，跳过第二次 _answer_questions，直接复用 check10d() 的结果。
    原因：两次 LLM 调用（各~48s）= 96s，阻塞 Hermes/QQ 事件循环。
    
    Args:
        complexity: "auto" | "simple" | "complex" | "critical" (default: "critical")
    
    注意：asyncio.run() 会与模块级后台线程冲突，
    所以这里直接同步调用 check10d，不做嵌套异步。
    """
    _ensure_started()
    base_result = check10d(task_text, agent_profile, complexity=complexity, emotion_state=emotion_state, user_id=user_id)

    # P1 Fix: simple 模式跳过二次分析，直接返回 check10d() 的结果
    if complexity == "simple":
        return base_result
    # 同步构建所有维度问题
    must = base_result["must_check"]
    important = base_result["important"]
    skipped = base_result["skipped"]
    dims_to_analyze = [d for d in DIMENSIONS if d.id in must or d.id in important]

    # 核心问题1修复：biography/experiences → 每个维度个性化
    # 1. 计算权重和追问（一次计算，所有维度共享）
    _profile_weights, _dim_prompts = inject_profile_into_dimensions(agent_profile, task_text)
    # 2. 高权重维度从 important 升级到 must（确保分析）
    if _profile_weights:
        boosted = [d_id for d_id, w in _profile_weights.items() if w >= 1.4 and d_id in important]
        for d_id in boosted:
            must = set(must)
            must.add(d_id)
            must = list(must)
    # 3. 每个维度使用个性化追问
    all_questions = {}
    for dim in dims_to_analyze:
        dim_result = _analyze_dim_sync(dim, task_text, agent_profile, _dim_prompts)
        all_questions.update(dim_result)

    # Pipeline 编排（同步版，复用 check10d 已构建的 ctx）
    _prior_adj = base_result.get("meta", {}).get("prior_adjustments", {})
    # 核心问题1修复：合并 biography 推断的权重到 prior_adjustments
    for dim_id, weight in _profile_weights.items():
        existing = _prior_adj.get(dim_id, 1.0)
        _prior_adj[dim_id] = existing * weight  # 乘数叠加
    # P0 FIX: base_result["task"] 是 merge_prompt_context() 的结果（含 unified_context）
    # 不再传 merge_prompt_context() 的拼接结果
    # 三路数据统一通过 inject_unified_profile → _profile_entries
    _merged_prompt = task_text  # 原始任务，profile 由 _answer_questions 注入
    _profile_entries = base_result.get("_profile_entries", []) or []
    _task_domain = classify_task_domain(task_text)
    _lessons_ctx = lessons_to_prompt(domain=_task_domain)
    # [MiniMind Compactor] 长上下文自动压缩
    _profile_entries, _lessons_ctx, _hist_ctx, _was_compact = _maybe_compact_ctx(
        _profile_entries, _lessons_ctx, base_result.get("history_context", "") or ""
    )
    # L3 感知层汇聚（web/scraping/rss/email/experiences 外部信号）
    try:
        from perception.summary import get_perception_summary
        _ps = get_perception_summary(task_topic=task_text, limit=10)
        _perception_ctx = _ps.to_prompt() if _ps else ""
    except Exception:
        _perception_ctx = ""
    # P1: DecisionStyle结构化影响（从base_result传入或重新推断）
    _decision_style = base_result.get("meta", {}).get("decision_style", "") or ""
    if not _decision_style:
        try:
            from judgment.honcho_soft_profile import infer_soft_profile
            _decision_style = infer_soft_profile(user_id).get("decision_style", "") or ""
        except Exception:
            _decision_style = ""
    answers = _answer_questions(_merged_prompt, all_questions, agent_profile,
                                _prior_adj, _hist_ctx, "", _profile_entries, _lessons_ctx,
                                _perception_ctx, pet_to_prompt(user_id), _decision_style)
    base_result["questions"] = all_questions
    base_result["answers"] = answers
    base_result["meta"]["checked"] = len([d.id for d in DIMENSIONS if d.id not in skipped])
    base_result["meta"]["parallel"] = False
    base_result["meta"]["prior_adjustments"] = _prior_adj
    base_result["meta"]["history_context"] = base_result.get("history_context", "")  # 保留，供输出参考
    # 末尾再次合成 verdict（用全部9维答案覆盖 check10d() 里的早期合成）
    verdict_str, confidence = _synthesize_verdict(task_text, answers)
    base_result["verdict"] = verdict_str
    base_result["confidence"] = confidence

    # [Anthropic Self-Verification] 检测维度间的逻辑矛盾
    try:
        _vf = _verify_judgment(task_text, answers, verdict_str, confidence)
        base_result["meta"]["verification_score"] = _vf["verification_score"]
        base_result["meta"]["verification_flags"] = _vf["flags"]
        base_result["meta"]["verification_warnings"] = _vf["warnings"]
        # 如果验证分数低，标记低质量判断
        if _vf["verification_score"] < 0.6:
            base_result["meta"]["low_quality_verdict"] = True
            base_result["meta"]["flags"].append("verdict_contradiction_detected")
    except Exception:
        base_result["meta"]["verification_score"] = 1.0
        base_result["meta"]["verification_flags"] = []
        base_result["meta"]["verification_warnings"] = []

    # [MiniMind Rep Penalty] 检测判决是否陷入重复
    try:
        from judgment.lessons import rep_penalty, is_repetitive
        _rp = rep_penalty(verdict_str)
        base_result["meta"]["repetition_penalty"] = round(_rp, 3)
        base_result["meta"]["is_repetitive"] = is_repetitive(verdict_str, threshold=0.3)
    except Exception:
        base_result["meta"]["repetition_penalty"] = 0.0
        base_result["meta"]["is_repetitive"] = False

    # predict-before-decision
    try:
        pred = predict_user_choice(task_text, answers, verdict_str, confidence)
        base_result["predicted_action"] = pred["predicted_action"]
        base_result["prediction_confidence"] = pred["prediction_confidence"]
        base_result["prediction_source"] = pred["source"]
    except Exception:
        base_result["predicted_action"] = verdict_str[:20]
        base_result["prediction_confidence"] = 0.40
        base_result["prediction_source"] = "error"

    # 【P0】将预测写入 judgment_snapshots（snapshot_judgment 已调用，补充字段）
    _chain_id = base_result.get("meta", {}).get("chain_id", "")
    if _chain_id:
        try:
            _c = _get_db_conn()
            _c.execute(
                "UPDATE judgment_snapshots SET verdict=?, confidence=?, predicted_action=?, prediction_confidence=? WHERE chain_id=?",
                (verdict_str[:300], confidence, base_result["predicted_action"][:200], base_result.get("prediction_confidence"), _chain_id)
            )
            _c.commit()
        except Exception:
            pass  # 不阻断返回

    # 经历层：判断完成后自动存为经历
    _chain_id2 = base_result.get("meta", {}).get("chain_id", "")
    try:
        save_experience(task_text, verdict_str, confidence, context=_history_ctx, user_id=user_id, chain_id=_chain_id2)
        # 途径3：行为日志（judgment 通道，无工具调用）
        log_agent_behavior(
            task_text=task_text,
            channel=ActionChannel.JUDGMENT,
            verdict=verdict_str,
            confidence=confidence,
            chain_id=base_result.get("meta", {}).get("chain_id", ""),
            tool_calls=[],
            execution_result="",
            user_id=user_id,
        )
    except Exception:
        pass  # 不阻断判断主流程

    # 【修复】check10d() 内部已通过 record_judgment() 调用过 snapshot_judgment()
    # 此处不再重复调用，避免 causal_chain 产生双重记录

    # ShortTermCache L1：会话内缓存（ZeusHammer 三层记忆）
    # 保存当前判断结果，供同会话内后续任务参考
    try:
        short_term_cache.set(
            f"judgment:{_chain_id2}",
            {
                "task": task_text,
                "verdict": verdict_str,
                "confidence": confidence,
                "emotion_pad": emotion_modulation.pad if emotion_modulation else None,
                "chain_id": _chain_id2,
            },
        )
    except Exception:
        pass

    # [Hermes Orange-Book] Progressive Disclosure 渐进揭示
    try:
        from judgment.progressive_disclosure import apply_disclosure
        _dr = apply_disclosure(
            task_text,
            base_result.get("answers", {}),
            verdict_str,
            confidence,
            base_result,
        )
        base_result["disclosure"] = {
            "layer": _dr.layer,
            "needs_confirm": _dr.needs_user_confirm,
            "user_prompt": _dr.user_prompt,
            "suggestions": _dr.suggestions,
            "reveal_dimensions": _dr.reveal_dimensions,
        }
        base_result["meta"]["disclosure_layer"] = _dr.layer
    except Exception:
        pass

    # 【问题3修复】闭环最后一步：记录 predicted_action 为 pending outcome
    # 这样下次早晨或 cron 可以 follow-up 确认实际执行情况
    try:
        from judgment.closed_loop import predict_outcome
        _chain_id3 = base_result.get("meta", {}).get("chain_id", "")
        _pred_action = base_result.get("predicted_action", "")
        if _chain_id3 and _pred_action:
            predict_outcome(_chain_id3, _pred_action)
    except Exception:
        pass  # 不阻断返回

    # 【便捷】将 chain_id 提到顶层，方便 CLI 直接访问
    base_result["chain_id"] = base_result.get("meta", {}).get("chain_id", "")
    return base_result


def check10d_and_execute(task_text: str, channel: str = "auto",
                          agent_profile=None) -> dict:
    """
    完整闭环：判断 → 执行 → 验证 → 进化
    
    三步合一：
    1. check10d_run() — 做判断
    2. ActionExecutor.execute() — 执行（benchmark/hermes/claude_code）
    3. verify_outcome() — 验证结果 → evolver
    
    Args:
        task_text: 判断任务
        channel: "auto" | "benchmark" | "hermes" | "claude_code"
        agent_profile: 可选人物画像
    
    Returns:
        {
            "judgment": check10d_run结果,
            "execution": ActionExecutor结果,
            "verdict": 判断结论,
            "outcome_score": 执行验证分 (0.0~1.0),
            "channel": 执行通道,
            "chain_id": 判断快照ID,
        }
    
    Example:
        result = check10d_and_execute("要不要辞职创业？", channel="benchmark")
        print(f"判断: {result['verdict']}")
        print(f"执行: {result['execution']['channel']}")
        print(f"得分: {result['outcome_score']}")
    """
    # Step 1: 做判断
    judgment_result = check10d_run(task_text, agent_profile)
    verdict = judgment_result.get("verdict", "")
    chain_id = judgment_result.get("meta", {}).get("chain_id", "")
    
    # Step 2: 执行（MiniMind RolloutEngine 多方案选最优）
    try:
        from action_system.action_executor import ActionRolloutEngine
        rollout_eng = ActionRolloutEngine()
        execution_result = rollout_eng.rollout_and_execute(
            task=task_text,
            verdict=verdict,
            user_context={"agent_profile": agent_profile} if agent_profile else None,
        )
    except Exception as e:
        execution_result = {"error": str(e), "outcome_score": 0.0, "channel": "none"}
    
    # Step 3: 验证结果已由 ActionExecutor._verify_and_feedback() 自动写入
    # 可直接通过 get_verification_stats() 查看
    
    return {
        "judgment": judgment_result,
        "execution": execution_result,
        "verdict": verdict,
        "outcome_score": execution_result.get("outcome_score", 0.0),
        "channel": execution_result.get("channel", "unknown"),
        "chain_id": chain_id,
        "expected": execution_result.get("expected", ""),
        "match": execution_result.get("match", False),
    }

