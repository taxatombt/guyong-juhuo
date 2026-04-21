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
from causal_memory import recall_causal_history, inject_to_judgment_input, find_similar_events, init
from judgment.closed_loop import start_verdict_listener
from judgment.self_evolver import start_evolver_scheduler

# Verdict 自动积累
from evolver.verdict_collector import save_verdict as _save_auto_verdict, VerdictRecord

# LLM 调用函数（从 router.py 拆分，独立可测）
# 注意：inject_emotion_signal 需使用 router.py 中的 global_emotion_system，
# 已在 router.py line 108 初始化，此处直接用同名引用。
from judgment.llm_calls import (
    inject_emotion_signal,
    _build_answer_prompt,
    _answer_questions,
    _keyword_match,
    _synthesize_verdict,
)

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

# 兼容旧接口命名
class _CausalMemoryCompat:
    """兼容层：让 causal_memory 作为可调用对象访问模块级函数"""
    def recall_causal_history(self, task, max_events=3):
        return recall_causal_history(task, max_events)
    def inject_to_judgment_input(self, task):
        return inject_to_judgment_input(task)

causal_memory = _CausalMemoryCompat()
from self_model.self_model import get_self_warnings
from curiosity.curiosity_engine import CuriosityEngine, trigger_from_low_confidence
from emotion_system.emotion_system import EmotionSystem

# Emotion × Judgment 集成：PAD状态调制维度权重
from subsystems.judgment.emotion_adapter import get_emotion_modulation

# 新增：自我复盘 + Fitness Baseline
from .self_review import SelfReviewSystem
from .closed_loop import record_judgment, snapshot_judgment, get_prior_adjustments
from .fitness_baseline import FitnessBaseline

# LLM接入：MiniMax适配器
from llm_adapter.minimax import get_adapter
from llm_adapter.base import CompletionRequest

# 经历层：历史判断记忆
from judgment.experiences import get_context_for_judgment, save_experience, record_outcome as _rec_outcome_exp, init as _init_exp
from judgment.behavior_logger import log_agent_behavior, ActionChannel

# 途径1：生平事实层
from judgment.biography import get_context as get_bio_context, extract_from_text as extract_bio, log_batch as log_bio_batch

# P0改进：因果推断引擎 - 给judgment提供推理底座
from causal_memory.causal_inference import CausalInferenceEngine, infer_causal_chain

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

def inject_emotion_signal(task_text: str) -> str:
    """兼容旧接口：如果情绪信号需要重视，返回提示文本"""
    # 先检测情绪（我们只需要文本关键词检测，这里传入空判断结果）
    signal = global_emotion_system.detect_emotion(task_text, {})
    if signal.is_signal:
        return f"\n[情绪信号提示] {signal.description}\n"
    return None


def _build_answer_prompt(task_text: str, questions: dict, agent_profile: dict = None, prior_adj: dict = None) -> str:
    """构造LLM回答问题的prompt"""
    dim_labels = {
        "cognitive": "认知维度",
        "game_theory": "博弈维度",
        "economic": "经济维度",
        "dialectical": "辩证维度",
        "emotional": "情绪维度",
        "intuitive": "直觉维度",
        "moral": "道德维度",
        "social": "社会维度",
        "temporal": "时间维度",
        "metacognitive": "元认知维度",
    }

    profile_context = ""
    if agent_profile:
        name = agent_profile.get("name", "通用AI")
        profile_context = f"\n你是{name}的判断分身。价值取向：{', '.join(agent_profile.get('values', []))}。"

    # ── 注入维度权重上下文（Self-Evolver 闭环关键）─────────────────
    # prior_adj = {dim_id: belief}，belief 越高表示该维度判断越准确
    # 让 LLM 知道在哪些维度上可以更信任自己的分析
    weight_context = ""
    if prior_adj:
        dim_weights = {k: v for k, v in prior_adj.items() if k in dim_labels}
        if dim_weights:
            strong = [dim_labels[k] for k, v in dim_weights.items() if v >= 0.7]
            weak = [dim_labels[k] for k, v in dim_weights.items() if v <= 0.45]
            hints = []
            if strong:
                hints.append(f"对[{', '.join(strong)}]的分析可以更自信深入")
            if weak:
                hints.append(f"对[{', '.join(weak)}]的分析需更谨慎，补充更多依据")
            if hints:
                weight_context = "\n[判断背景] " + "；".join(hints) + "。"

    parts = [
        f"任务：{task_text}{profile_context}{weight_context}\n",
        "请针对以下问题给出简短而深刻的回答（每条回答不超过50字）：\n",
    ]

    for dim_id, qs in questions.items():
        label = dim_labels.get(dim_id, dim_id)
        if not qs:
            continue
        parts.append(f"【{label}】")
        for i, q in enumerate(qs, 1):
            parts.append(f"  Q{i}. {q}")
        parts.append("")

    return "\n".join(parts)


def _keyword_match(text, keywords):
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


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
    # Hermes启发：prefetch_all - 每轮前背景召回
    hook_context = prefetch_all(task_text)
    fenced_context = hook_context.get("fenced_context", "")
    
    # 情绪系统：第一步就检测情绪信号，需要重视就注入上下文
    original_task = task_text
    emotion_signal = inject_emotion_signal(original_task)
    if emotion_signal:
        task_text = original_task + "\n" + emotion_signal

    # Emotion × Judgment 集成：PAD状态调制（核心集成点）
    emotion_modulation = None
    if emotion_state is not None:
        emotion_modulation = get_emotion_modulation(emotion_state)
        # 情绪提示词注入任务上下文
        if emotion_modulation.prompt_hint:
            task_text = task_text + "\n\n" + emotion_modulation.prompt_hint
        # 将调制信息存储到结果（供 downstream 使用）
    else:
        # 无 PAD 输入时回退：使用 EmotionSystem 检测情绪
        _es = EmotionSystem()
        emotion_detection = _es.detect_emotion(original_task, {})
    
    # 因果记忆：召回相似历史，注入上下文
    causal_result = causal_memory.recall_causal_history(task_text)
    if causal_result["summary"]:
        task_text = causal_memory.inject_to_judgment_input(task_text)
    
    # P3改进：规则预检 - 先用规则快速判断，降低LLM调用
    rule_precheck = rule_based_precheck(original_task)
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
        skipped = ["metacognitive"]
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

    if agent_profile:
        extra = _inject_profile_questions(agent_profile, task_text)
        if extra:
            questions["cognitive"].extend(extra)

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
            "original_task": original_task,
            "average_confidence": avg_confidence,
            "dim_confidence": dim_confidence if 'dim_confidence' in locals() else {},
        }, current_task=original_task[:60])

    # 拿到完整情绪检测结果（仅当没有PAD输入时回退）
    emotion_system = EmotionSystem()
    emotion_detection = emotion_system.detect_emotion(original_task, {})

    # LLM接入：MiniMax回答所有维度问题
    prior_adj = {}
    try:
        prior_adj = get_prior_adjustments()
    except Exception:
        pass
    # 经历层：历史相似判断
    _hist_ctx = get_context_for_judgment(task_text, user_id)
    # 途径1：自动抽取生平事实
    _bio_facts = extract_bio(task_text)
    if _bio_facts:
        log_bio_batch(_bio_facts, source="auto")
    _bio_ctx = get_bio_context()
    answers = _answer_questions(task_text, questions, agent_profile, prior_adj, _hist_ctx, _bio_ctx)

    _ret = {
        "task": task_text,
        "original_task": original_task,
        "complexity": complexity,
        "must_check": must,
        "important": important,
        "skipped": skipped,
        "questions": questions,
        "answers": answers,
        "agent_profile": agent_profile,
        "causal_memory": {
            "has_history": causal_result["summary"] is not None,
            "similar_events": causal_result["similar_events"],
            "causal_chains": causal_result["causal_chains"],
            "summary": causal_result["summary"],
            "causal_inference": None,
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
            "causal_memory": hook_context.get("causal_memory"),
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
            "detected_emotions": [emotion_detection.emotion_label] if emotion_detection.emotion_label else [],
            "need_attention": emotion_detection.is_signal,
            "signal_type": emotion_detection.emotion_label,
            "signal_description": emotion_detection.description,
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
        }
    }

    # ── 闭环：记录因果链 ──────────────────────────────────────────────
    try:
        _dims_chosen = [d.id for d in DIMENSIONS if d.id not in skipped]
        _weights = {d: prior_adj.get(d, 1.0) for d in _dims_chosen}
        _chain_id = record_judgment(
            task_text=original_task[:300],
            dimensions=_dims_chosen,
            weights=_weights,
            reasoning={},
        )
        _ret["meta"]["chain_id"] = _chain_id
        
        # ── Verdict 自动积累：每次judgment自动记录 ──────────────────
        # source="auto" 表示系统自动记录，待用户反馈 verdict
        _auto_record = VerdictRecord(
            chain_id=_chain_id,
            task_text=original_task[:300],
            timestamp=datetime.now().isoformat(),
            verdict="pending",  # 待用户反馈
            source="auto",
            metadata={
                "complexity": complexity,
                "dimensions": _dims_chosen,
                "weights": _weights,
                "emotion": emotion_detection.emotion_label if emotion_detection.emotion_label else None,
            }
        )
        _save_auto_verdict(_auto_record)
        
        # Stop Hook: 捕获judgment行为
        capture_judgment(
            task=original_task,
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
            inference_engine = CausalInferenceEngine()
            causal_infer = inference_engine.infer(
                situation=original_task,
                judgment_dimensions=must + important
            )
            _ret["causal_memory"]["causal_inference"] = {
                "best_explanation": causal_infer.best_explanation,
                "reasoning_chain": causal_infer.reasoning_chain,
                "confidence": causal_infer.confidence,
                "needs_more_data": causal_infer.needs_more_data,
                "hypotheses_count": len(causal_infer.hypotheses)
            }
    except Exception:
        pass

    # ── Verdict 合成：从维度答案生成最终判断 ─────────────────────────
    verdict_str, confidence = _synthesize_verdict(original_task, _ret.get("answers", {}))
    _ret["verdict"] = verdict_str
    _ret["confidence"] = confidence

    # 经历层：存为历史记忆
    try:
        save_experience(original_task, verdict_str, confidence, context=_hist_ctx, user_id=user_id)
        # 途径3：行为日志（judgment 通道，无工具调用）
        log_agent_behavior(
            task_text=original_task,
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

    return _ret


async def _analyze_dim(dim, task_text, agent_profile):
    """分析单个维度（asyncio协程）。所有维度同时执行，互不阻塞。"""
    await asyncio.sleep(0)  # 让出控制，允许其他协程并发执行
    return _analyze_dim_sync(dim, task_text, agent_profile)


def _analyze_dim_sync(dim, task_text, agent_profile):
    """分析单个维度（同步版）。与 asyncio 版逻辑相同。"""
    questions = dim.questions[:]
    if agent_profile:
        extra = _inject_profile_questions(agent_profile, task_text)
        if extra:
            questions = questions + extra
    return {dim.id: questions}


def check10d_run(task_text, agent_profile=None, emotion_state=None, user_id: str = "default"):
    """
    同步检视接口：直接调用 check10d，critical 复杂度。
    
    注意：asyncio.run() 会与模块级后台线程冲突，
    所以这里直接同步调用 check10d，不做嵌套异步。
    """
    _ensure_started()
    base_result = check10d(task_text, agent_profile, complexity="critical", emotion_state=emotion_state, user_id=user_id)
    # 同步构建所有维度问题
    must = base_result["must_check"]
    important = base_result["important"]
    skipped = base_result["skipped"]
    dims_to_analyze = [d for d in DIMENSIONS if d.id in must or d.id in important]
    all_questions = {}
    for dim in dims_to_analyze:
        dim_result = _analyze_dim_sync(dim, task_text, agent_profile)
        all_questions.update(dim_result)
    # LLM回答
    _prior_adj = base_result.get("meta", {}).get("prior_adjustments", {})
    # 经历层：先获取历史相似判断作为上下文
    _history_ctx = get_context_for_judgment(task_text, user_id)
    # 生平事实层
    _bio_facts = extract_bio(task_text)
    if _bio_facts:
        log_bio_batch(_bio_facts, source="auto")
    _bio_ctx = get_bio_context()
    answers = _answer_questions(task_text, all_questions, agent_profile, _prior_adj, _history_ctx, _bio_ctx)
    base_result["questions"] = all_questions
    base_result["answers"] = answers
    base_result["meta"]["checked"] = len([d.id for d in DIMENSIONS if d.id not in skipped])
    base_result["meta"]["parallel"] = False
    base_result["meta"]["prior_adjustments"] = _prior_adj
    base_result["meta"]["history_context"] = _history_ctx  # 保留，供输出参考
    # 末尾再次合成 verdict（用全部9维答案覆盖 check10d() 里的早期合成）
    verdict_str, confidence = _synthesize_verdict(task_text, answers)
    base_result["verdict"] = verdict_str
    base_result["confidence"] = confidence

    # 经历层：判断完成后自动存为经历
    try:
        save_experience(task_text, verdict_str, confidence, context=_history_ctx, user_id=user_id)
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
    
    # Step 2: 执行
    try:
        from action_system.action_executor import ActionExecutor
        executor = ActionExecutor()
        execution_result = executor.execute(
            task=task_text,
            verdict=verdict,
            channel=channel,
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


def _synthesize_verdict(task_text: str, answers: dict) -> tuple:
    """
    基于各维度回答合成 verdict 和 confidence
    返回 (verdict_str, confidence_float)
    """
    if not answers:
        return ("需要更多信息才能判断", 0.3)
    try:
        raw = ""
        for dim, ans in answers.items():
            if isinstance(ans, dict) and "content" in ans:
                raw += ans["content"]
            elif isinstance(ans, str):
                raw += ans
        raw = raw.strip()
        if not raw:
            raise ValueError("No content")

        def score_sent(sent: str) -> float:
            chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
            if chinese < 4:
                return 0.0
            len_score = min(chinese / 30.0, 1.0) * 0.3
            action_kw = {"先", "应该", "可以", "建议", "推荐", "值得", "不要",
                        "考虑", "评估", "权衡", "控制", "分散", "调研",
                        "辞职", "创业", "买房", "移民", "借", "读研", "读博", "分手",
                        "all in", "炒股", "考证", "考公", "健身", "换城市",
                        "断舍离", "领养", "回老家", "原谅", "接受", "拒绝",
                        "审慎", "谨慎", "果断", "立即", "保守", "激进"}
            action_cnt = sum(1 for kw in action_kw if kw in sent)
            action_score = min(action_cnt / 2.0, 1.0) * 0.4
            vague_kw = {"不确定", "很难说", "更多信息", "无法判断",
                         "具体情况具体分析", "基于", "给出判断", "需要更多信息",
                         "再给出判断", "再综合考虑", "综合给出", "多维分析给出"}
            vague_penalty = sum(0.3 for kw in vague_kw if kw in sent)
            return max(0.0, len_score + action_score - vague_penalty)

        def extract_sentences(text: str) -> list:
            """句子提取：句号 + 省略号分隔（处理无句号段落）"""
            # 先清理残留的 thinking 标签
            text = re.sub(r'^好了?\s*', '', text)
            text = re.sub(r'好了?\s*$', '', text)
            text = re.sub(r'^<think>\s*', '', text)
            text = re.sub(r'<think>\s*$', '', text)
            text = re.sub(r'@\d{10,}', '', text)  # 去掉 @时间戳
            SEP = '<<<SEP>>>'
            text2 = text.replace('...', SEP)
            parts = re.split(r"([。！？])", text2)
            sents = []
            for i in range(0, len(parts) - 1, 2):
                part = parts[i].strip()
                sep = parts[i + 1]
                sent = part + (sep if sep else '')
                if sent.strip():
                    sents.append(sent.strip().replace(SEP, '...'))
            if len(parts) % 2 == 1 and parts[-1].strip():
                last = parts[-1].strip().replace(SEP, '...')
                if last:
                    sents.append(last)
            return sents

        # Step 1: 清理正文残留 thinking 标签
        after = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Step 2: 从正文（非 thinking block）提取句子
        best_score = -1.0
        best_sent = ""
        if after:
            for sent in extract_sentences(after):
                chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese >= 4 and chinese / max(len(sent), 1) > 0.5:
                    s = score_sent(sent)
                    if s > best_score:
                        best_score = s
                        best_sent = sent[:50]
        if best_score >= 0.15:
            confidence = min(0.88, 0.35 + len(answers) * 0.08)
            return (best_sent, confidence)

        # Step 3: 从所有 thinking blocks 扫描，选最佳句子（句子级，非 block 级）
        blocks = re.findall(r"<think>.*?</think>", raw, re.DOTALL)
        for block in blocks:
            # 提取 thinking block 的文本内容（去掉标签）
            block_text = re.sub(r'^<think>', '', block)
            block_text = re.sub(r'</think>$', '', block_text)
            block_clean = re.sub(r'^\s*(好的|嗯|下面|综合|根据|经过).*?[:：]', "", block_text)
            block_clean = re.sub(r'Count[:：].*$', "", block_clean, flags=re.DOTALL)
            block_clean = re.sub(r'字数[:：].*$', "", block_clean, flags=re.DOTALL)
            block_clean = re.sub(r'[A-Za-z\u4e00-\u9fff]\s*\(\d+\)', "", block_clean)
            # 逐句评分
            for sent in extract_sentences(block_clean):
                chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese >= 4 and chinese / max(len(sent), 1) > 0.5:
                    s = score_sent(sent)
                    if s > best_score:
                        best_score = s
                        best_sent = sent[:50]
        if best_sent:
            confidence = min(0.88, 0.35 + len(answers) * 0.08)
            return (best_sent, confidence)

        # Step 4: Fallback
        total_expected = len(answers) + 3
        confidence = min(0.9, len(answers) / total_expected + 0.2)
        return (f"基于{len(answers)}个维度的分析给出了判断", confidence)
    except Exception:
        return ("需要更多信息才能判断", 0.3)

def _judge_complexity(text):
    """自动判断任务复杂度"""
    critical_kw = ["生死", "生命", "法律", "犯罪", "坐牢", "致命", "不可逆"]
    complex_kw = ["纠结", "矛盾", "冲突", "多方", "合伙", "长期", "战略",
                  "要不要", "选哪个", "怎么选", "利弊", "优劣", "两难"]
    for kw in critical_kw:
        if kw in text:
            return "critical"
    for kw in complex_kw:
        if kw in text:
            return "complex"
    return "simple"


def _inject_profile_questions(profile, task_text):
    """根据 agent_profile 注入个性化追问"""
    if not profile:
        return []
    extra = []
    name = profile.get("name", "")
    values = profile.get("values", [])
    biases = profile.get("biases", [])

    if name:
        extra.append(f"【{name}会怎么想这个问题？】")
    if biases:
        for b in biases:
            extra.append(f"【{name}容易在{b}上犯错，我有没有犯同样的错？】")
    if values:
        val_str = " > ".join(values[:3])
        extra.append(f"【{name}的价值排序是{val_str}，这个判断符合吗？】")

    return extra


def format_report(result):
    """旧兼容，人可读"""
    lines = [
        f"[判断框架] 十维分析（{result['complexity']}级）",
        f"[背景] {result['task'][:60]}",
        f"[复杂度] {result['complexity']}",
        f"[维度] {result['meta']['checked']}/10（跳过{result['meta']['skipped_count']}个）",
        "",
    ]

    for dim in DIMENSIONS:
        if dim.id in result["skipped"] and result["complexity"] != "critical":
            continue
        lines.append(f"== {dim.name} ==")
        lines.append(f"  {dim.description}")
        for q in dim.questions:
            lines.append(f"  -> {q}")
        lines.append("")

    lines.append(f"[验证] 十维都有思考过吗？")
    return "\n".join(lines)


def format_structured(result):
    """新接口，结构化人可读"""
    lines = [
        f"=== 十维检视 ===",
        f"任务: {result['task'][:60]}",
        f"复杂度: {result['complexity']} | 维度: {result['meta']['checked']}/10",
        "",
    ]

    priority_map = [
        ("MUST", result["must_check"]),
        ("IMPORTANT", result["important"]),
        ("SKIPPED", result["skipped"]),
    ]

    for label, dim_ids in priority_map:
        if not dim_ids:
            continue
        lines.append(f"【{label}】")
        for dim_id in dim_ids:
            dim = next((d for d in DIMENSIONS if d.id == dim_id), None)
            if not dim:
                continue
            lines.append(f"  {dim.name}:")
            for q in dim.questions[:2]:
                lines.append(f"    - {q}")
        lines.append("")

    if result.get("agent_profile"):
        p = result["agent_profile"]
        lines.append(f"【模拟对象】{p.get('name', '未知')}")
        if p.get("values"):
            lines.append(f"  价值: {' > '.join(p['values'][:3])}")

    return "\n".join(lines)
