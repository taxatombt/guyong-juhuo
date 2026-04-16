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
from paths import PATHS
from judgment.dimensions import DIMENSIONS
from causal_memory import recall_causal_history, inject_to_judgment_input, find_similar_events, init

# 初始化
init()

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

# 新增：自我复盘 + Fitness Baseline
from .self_review import SelfReviewSystem
from .closed_loop import record_judgment, snapshot_judgment, get_prior_adjustments
from .fitness_baseline import FitnessBaseline

# LLM接入：MiniMax适配器
from llm_adapter.minimax import get_adapter
from llm_adapter.base import CompletionRequest

# P0改进：因果推断引擎 - 给judgment提供推理底座
from causal_memory.causal_inference import CausalInferenceEngine, infer_causal_chain

# P3改进：十维推理规则引擎
from .judgment_rules import rule_based_precheck, get_rule_scores

# Stop Hook：事件捕获
from .stop_hook import capture_judgment, capture_verdict, finalize_session

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


def _build_answer_prompt(task_text: str, questions: dict, agent_profile: dict = None) -> str:
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

    parts = [
        f"任务：{task_text}{profile_context}\n",
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


def _answer_questions(task_text: str, questions: dict, agent_profile: dict = None) -> dict:
    """调用MiniMax LLM回答所有维度问题，返回 {dim_id: answer_text, ...}"""
    adapter = get_adapter()

    # 如果没有配置api_key（环境变量也没有），返回空
    if not adapter.is_configured():
        print("[LLM] MiniMax未配置 api_key，跳过answer生成")
        return {}

    prompt = _build_answer_prompt(task_text, questions, agent_profile)

    # 截断prompt（LLM context limit）
    if len(prompt) > 6000:
        prompt = prompt[:6000] + "\n[内容过长已截断]"

    try:
        response = adapter.complete(CompletionRequest(
            prompt=prompt,
            max_tokens=2048,
            temperature=0.7,
        ))

        if not response.success:
            print(f"[LLM] 调用失败: {response.error}")
            return {}

        # 简单按行解析：格式为 "【维度名】回答内容"
        answers = {}
        current_dim = None
        current_content = []

        dim_labels_inv = {
            "认知维度": "cognitive",
            "博弈维度": "game_theory",
            "经济维度": "economic",
            "辩证维度": "dialectical",
            "情绪维度": "emotional",
            "直觉维度": "intuitive",
            "道德维度": "moral",
            "社会维度": "social",
            "时间维度": "temporal",
            "元认知维度": "metacognitive",
        }

        for line in response.content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 检测维度标题行
            matched_dim = None
            for label, dim_id in dim_labels_inv.items():
                if label in line:
                    matched_dim = dim_id
                    break

            if matched_dim:
                # 保存上一维度的答案
                if current_dim and current_content:
                    answers[current_dim] = " ".join(current_content).strip()
                current_dim = matched_dim
                current_content = []
                # 去除标题，只保留后面的内容
                rest = line.split("】", 1)
                if len(rest) > 1:
                    content = rest[1].strip()
                    if content:
                        current_content.append(content)
            elif current_dim and line:
                # 普通内容行，拼接到当前维度
                current_content.append(line)

        # 保存最后一个维度
        if current_dim and current_content:
            answers[current_dim] = " ".join(current_content).strip()

        return answers

    except Exception as e:
        print(f"[LLM] 回答生成异常: {e}")
        return {}


# 维度优先级分类
# 优先级原则（聚活项目设计）：
# - game_theory / emotional 永远必检（人类最常踩这俩坑）
# - economic / cognitive 基础维度
MUST_CHECK = ["game_theory", "emotional", "cognitive", "economic"]
IMPORTANT = ["dialectical", "intuitive", "moral", "social"]
NICE_TO_HAVE = ["temporal", "metacognitive"]


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


def check10d(task_text, agent_profile=None, complexity="auto"):
    """
    标准化接口：十维检视
    因果记忆：自动注入相关历史判断到任务上下文

    参数:
        task_text: 任务描述
        agent_profile: 可选dict {
            "name": "<persona>",           # 模拟对象
            "values": ["成就", "自由"],  # 价值排序
            "biases": ["过度分析"],      # 已知偏差
            "style": "理性优先"          # 思考风格
        }
        complexity: "auto" | "simple" | "complex" | "critical"

    返回:
        {
            "task": str,
            "original_task": str,
            "complexity": str,
            "must_check": [dim_id, ...],
            "important": [dim_id, ...],
            "skipped": [dim_id, ...],
            "questions": {dim_id: [str, ...], ...},
            "answers": {},
            "agent_profile": agent_profile,
            "causal_memory": causal_result,
            "meta": {
                "total_dims": 10,
                "checked": int,
                "skipped_count": int,
            }
        }
    """
    # 情绪系统：第一步就检测情绪信号，需要重视就注入上下文
    original_task = task_text
    emotion_signal = inject_emotion_signal(original_task)
    if emotion_signal:
        task_text = original_task + "\n" + emotion_signal
    
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

    # 拿到完整情绪检测结果
    from emotion_system.emotion_system import EmotionSystem
    emotion_system = EmotionSystem()
    emotion_detection = emotion_system.detect_emotion(original_task, {})

    # LLM接入：MiniMax回答所有维度问题
    prior_adj = {}
    try:
        prior_adj = get_prior_adjustments()
    except Exception:
        pass
    answers = _answer_questions(task_text, questions, agent_profile)

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
    return _ret


async def _analyze_dim(dim, task_text, agent_profile):
    """分析单个维度（asyncio协程）。所有维度同时执行，互不阻塞。"""
    await asyncio.sleep(0)  # 让出控制，允许其他协程并发执行
    questions = dim.questions[:]
    if agent_profile:
        extra = _inject_profile_questions(agent_profile, task_text)
        if extra:
            questions = questions + extra
    return {dim.id: questions}


def check10d_run(task_text, agent_profile=None):
    """
    并行检视接口：asyncio并行执行10维度分析（critical模式专用）
    
    原理：10个维度同时分析，通过asyncio.gather并发执行
    预期加速：5-10倍（vs串行逐维等待）
    
    同步接口，内部用asyncio.run()处理并发
    """
    async def _run():
        base_result = check10d(task_text, agent_profile, complexity="critical")
        must = base_result["must_check"]
        important = base_result["important"]
        skipped = base_result["skipped"]

        dims_to_analyze = [
            d for d in DIMENSIONS
            if d.id in must or d.id in important
        ]

        if len(dims_to_analyze) > 1:
            tasks = [_analyze_dim(dim, task_text, agent_profile) for dim in dims_to_analyze]
            dim_results_list = await asyncio.gather(*tasks)
        else:
            dim_results_list = [await _analyze_dim(dims_to_analyze[0], task_text, agent_profile)]

        all_questions = {}
        for dr in dim_results_list:
            all_questions.update(dr)

        # LLM接入：MiniMax回答所有维度问题
        _prior_adj = base_result.get("meta", {}).get("prior_adjustments", {})
        answers = _answer_questions(task_text, all_questions, agent_profile)

        base_result["questions"] = all_questions
        base_result["answers"] = answers
        base_result["meta"]["checked"] = len([d.id for d in DIMENSIONS if d.id not in skipped])
        base_result["meta"]["parallel"] = True
        base_result["meta"]["prior_adjustments"] = _prior_adj
        return base_result

    return asyncio.run(_run())


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
