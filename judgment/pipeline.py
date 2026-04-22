"""
pipeline.py — Judgment Pipeline 编排层

每个注入器独立函数，router.py 只做编排：
    ctx = JudgmentContext(task, ...)
    ctx = inject_biography(ctx)
    ctx = inject_experiences(ctx)
    ctx = inject_causal_memory(ctx)
    ctx = inject_emotion(ctx)
    ctx = inject_self_model(ctx)
    return llm_judge(ctx)

每个 injector 返回 ctx（修改后的），链式调用。
"""
from typing import Optional, Dict, Any
from .context import JudgmentContext

# Lazy imports — 避免循环依赖
_lazy_imports = {}


def _lazy(name: str, path: str):
    """延迟导入，注入器级懒加载"""
    if name not in _lazy_imports:
        import importlib
        mod, attr = path.rsplit('.', 1)
        module = importlib.import_module(mod)
        _lazy_imports[name] = getattr(module, attr)
    return _lazy_imports[name]


# ════════════════════════════════════════════════════════════════════════════
# Injector 1: Biography — 途径1，生平事实
# ════════════════════════════════════════════════════════════════════════════

def inject_biography(ctx: JudgmentContext) -> JudgmentContext:
    """
    途径1注入：
    1. 从当前任务抽取生平事实
    2. 写入 biography 表
    3. 返回生平上下文字符串
    """
    from .biography import extract_bio, get_bio_context, log_bio_batch
    
    facts = extract_bio(ctx.task_text)
    if facts:
        log_bio_batch(facts, source="auto")
    ctx.bio_facts = facts
    ctx.bio_context = get_bio_context()
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Injector 2: Experiences — 途径2，历史相似判断
# ════════════════════════════════════════════════════════════════════════════

def inject_experiences(ctx: JudgmentContext) -> JudgmentContext:
    """
    途径2注入：
    1. 查找用户的历史相似判断
    2. 生成"这个用户（你）遇到过类似情况"上下文
    """
    from .experiences import get_context_for_judgment
    
    ctx.history_context = get_context_for_judgment(ctx.task_text, ctx.user_id)
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Injector 3: Causal Memory — 途径3，因果记忆
# ════════════════════════════════════════════════════════════════════════════

def inject_causal_memory(ctx: JudgmentContext) -> JudgmentContext:
    """
    途径3注入：
    1. 召回相似历史事件
    2. 注入到判断上下文
    """
    from causal_memory import recall_causal_history, inject_to_judgment_input
    
    causal_result = recall_causal_history(ctx.task_text)
    ctx.causal_result = causal_result
    
    if causal_result.get("summary"):
        ctx.causal_context = inject_to_judgment_input(ctx.task_text)
        ctx.task_text = causal_result.get("task_with_context", ctx.task_text)
    
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Injector 4: Emotion — 情绪 PAD 调制
# ════════════════════════════════════════════════════════════════════════════

def inject_emotion(ctx: JudgmentContext) -> JudgmentContext:
    """
    情绪注入：
    1. 如果传入了 emotion_state（PAD），用指定状态
    2. 否则用 EmotionSystem 自动检测
    3. 生成情绪调制提示词
    """
    from subsystems.judgment.emotion_adapter import get_emotion_modulation
    from emotion_system.emotion_system import EmotionSystem
    
    if ctx.emotion_state:
        emotion_modulation = get_emotion_modulation(ctx.emotion_state)
        ctx.emotion_modulation = emotion_modulation
        if emotion_modulation.prompt_hint:
            ctx.emotion_hint = emotion_modulation.prompt_hint
    else:
        es = EmotionSystem()
        ctx.emotion_detection = es.detect_emotion(ctx.original_task, {})
    
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Injector 5: Self Model — 自我模型，动态权重
# ════════════════════════════════════════════════════════════════════════════

def inject_self_model(ctx: JudgmentContext) -> JudgmentContext:
    """
    自我模型注入：
    1. 获取 prior_adjustments（各维度动态权重）
    2. 获取自我警告和强项
    """
    from subsystems.judgment.closed_loop import get_prior_adjustments
    
    try:
        ctx.prior_adjustments = get_prior_adjustments()
    except Exception:
        pass
    
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Injector 6: UserModel — 三路汇聚层（L1+L2+L3+矛盾检测+时间衰减）
# ════════════════════════════════════════════════════════════════════════════

def inject_user_model(ctx: JudgmentContext) -> JudgmentContext:
    """
    UserModel 汇聚层注入：
    1. 从 biography（L1）、experiences（L2）、causal_memory（L3）获取结构化数据
    2. 时间衰减：fact 半衰期 365天，pattern 半衰期 180天
    3. 矛盾检测：L1 claim vs L2 pattern 检测
    4. 按任务相关性过滤
    5. 合成 unified_context 覆盖旧三路上下文

    运行在 L1/L2/L3 注入器之后。
    """
    try:
        from .user_model import UserModel
        um = UserModel()
        unified_ctx = um.get_context_for_task(ctx.task_text, ctx.user_id)
        unified_text = um.synthesize(unified_ctx, ctx.task_text)
        ctx.unified_context = unified_text

        # 矛盾标记存到 ctx（供 downstream 使用）
        if unified_ctx.contradictions:
            ctx.skipped_dimensions = getattr(ctx, 'skipped_dimensions', [])
            for c in unified_ctx.contradictions:
                ctx.skipped_dimensions.append(
                    f"contradiction:{c.l1_claim[:30]} vs {c.l2_behavior[:30]}"
                )
    except Exception as e:
        # 降级：不阻断判断流程
        pass

    return ctx


# ════════════════════════════════════════════════════════════════════════════
# Prefetch — 每轮前背景召回（Hermes 启发）
# ════════════════════════════════════════════════════════════════════════════

def prefetch(task_text: str) -> Dict[str, Any]:
    """
    每轮判断前，召回 hook / fitness / instinct 上下文。
    返回 hook_context 字符串。
    """
    try:
        from .life_cycle_hooks import on_turn_start
        result = on_turn_start(task_text)
        return result or {}
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════════════════════
# Pipeline 编排入口
# ════════════════════════════════════════════════════════════════════════════

def check10d_full(task_text: str, config: dict = None) -> dict:
    """
    全量 pipeline 判断（供 MCP server 等外部调用）。

    流程：
        1. prefetch() — 预取 biography/experiences/emotion/self_model
        2. run_pipeline() — 注入全部上下文
        3. 返回完整结果（verdict + dimensions + confidence + chain_id）

    Args:
        task_text: 判断问题
        config: 可选配置（目前未使用，保留接口兼容）

    Returns:
        dict，含 verdict/confidence/chain_id/dimensions
    """
    from judgment.router import check10d_run
    return check10d_run(task_text)


def PipelineConfig(**kwargs):
    """占位配置类（MCP 调用用）"""
    return kwargs


def format_full_report(result: dict) -> str:
    """格式化完整报告"""
    from judgment.router import format_report
    return format_report(result)


def run_pipeline(ctx: JudgmentContext) -> JudgmentContext:
    """
    完整编排：按顺序执行所有注入器。
    router.py 的 check10d 只调用这一句。
    """
    ctx = inject_emotion(ctx)
    ctx = inject_biography(ctx)
    ctx = inject_experiences(ctx)
    ctx = inject_causal_memory(ctx)
    ctx = inject_self_model(ctx)
    ctx = inject_user_model(ctx)
    return ctx
