"""
pipeline.py — Judgment Pipeline 编排层

单一汇聚：inject_unified_profile = 三路（biography + experiences + correlation_memory）
          + 矛盾检测 + 时间衰减

router.py 只调用 run_pipeline：
    ctx = run_pipeline(ctx)
        → inject_emotion        (情绪 PAD 调制)
        → inject_unified_profile (三路合一汇聚)
        → inject_self_model     (动态权重 prior_adjustments)
        → inject_user_model     (矛盾标记 + 向后兼容)
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
# ════════════════════════════════════════════════════════════════════════════
# ────────────────────────────────────────────────────────────────────────
# 三路(传记+经历+感知) → UnifiedProfile → router
# ════════════════════════════════════════════════════════════════════════════

def inject_unified_profile(ctx: JudgmentContext) -> JudgmentContext:
    """
    单一汇聚层。三路都是它的输入，router 只读它的输出。

    L1 biographical_facts（带时间衰减，半衰期 365d）
    L2 experiences（带 outcome_score，半衰期 180d）
    L3 perception_intents（带 relevance，半衰期 30d）

    生成：
      ctx._unified_context_obj: UnifiedContext（结构化）
      ctx._profile_entries: List[ProfileEntry]（已排序、带矛盾flag）
      ctx.unified_profile: UnifiedProfile 对象（to_prompt 按维度提取）
      ctx.unified_context: str（供 merge_prompt_context 旧接口兼容）

    矛盾处理：
      L1 claim vs L2 behavior → priority=3，contradiction_flag=True
      Self-report bias：Kahneman System 1/2 → 行为数据 > 自我报告
    """
    from judgment.user_model import UserModel, UnifiedProfile

    # ① 传记抽取：从当前任务提取新 fact，写入 biography 表
    # （inject_biography 的职责，已合并进本 injector）
    try:
        from .biography import extract_bio, log_bio_batch
        new_facts = extract_bio(ctx.task_text)
        if new_facts:
            log_bio_batch(new_facts, source="auto")
        ctx.bio_facts = new_facts or []
    except Exception:
        ctx.bio_facts = []

    um = UserModel(user_id=ctx.user_id)

    # ② 读取三路数据 → UnifiedContext（结构化）
    ctx_uc = um.get_context_for_task(ctx.task_text, ctx.user_id)

    # 生成 ProfileEntry 列表（已排序：L1>L2>L3，矛盾fact→priority=3）
    entries = um.generate_profile(ctx_uc, ctx.task_text)

    # 矛盾时自动回写 biography 表（Self-Evolver 反馈）
    if ctx_uc.contradictions:
        for contradiction in ctx_uc.contradictions:
            try:
                from judgment.user_model import update_profile_on_contradiction
                update_profile_on_contradiction(contradiction, ctx_uc)
            except Exception:
                pass

    ctx._unified_context_obj = ctx_uc
    ctx._profile_entries = entries
    ctx.unified_profile = UnifiedProfile()

    # 兼容文本（merge_prompt_context 旧接口，降级用）
    ctx.unified_context = um.synthesize(ctx_uc, ctx.task_text)

    # 旧字段也设置（向后兼容）
    ctx.bio_context = ""      # 不再单独注入，由 unified_profile 统一管理
    ctx.history_context = ""  # 同上
    ctx.causal_context = ""   # 同上

    return ctx


# ════════════════════════════════════════════════════════════════════════════
# ────────────────────────────────────────────────────────────────────────
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
        # 如果是字符串（"happy"/"calm"/"anxious"），转换为 PAD dict
        if isinstance(ctx.emotion_state, str):
            _EMOTION_PAD = {
                "happy": {"P": 0.8, "A": 0.4, "D": 0.5},
                "sad": {"P": -0.7, "A": -0.2, "D": 0.3},
                "anxious": {"P": -0.5, "A": 0.6, "D": -0.3},
                "calm": {"P": 0.4, "A": -0.2, "D": 0.6},
                "excited": {"P": 0.8, "A": 0.7, "D": 0.4},
                "angry": {"P": -0.7, "A": 0.6, "D": -0.5},
                "fear": {"P": -0.6, "A": 0.5, "D": -0.4},
                "frustrated": {"P": -0.5, "A": 0.3, "D": -0.4},
            }
            ctx.emotion_state = _EMOTION_PAD.get(ctx.emotion_state.lower(), {"P": 0.0, "A": 0.0, "D": 0.0})
        emotion_modulation = get_emotion_modulation(ctx.emotion_state)
        ctx.emotion_modulation = emotion_modulation
        if emotion_modulation.prompt_hint:
            ctx.emotion_hint = emotion_modulation.prompt_hint
    else:
        es = EmotionSystem()
        ctx.emotion_detection = es.detect_emotion(ctx.original_task, {})
    
    return ctx


# ════════════════════════════════════════════════════════════════════════════
# ────────────────────────────────────────────────────────────────────────
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
# ────────────────────────────────────────────────────────────────────────（L1+L2+L3+矛盾检测+时间衰减）
# ════════════════════════════════════════════════════════════════════════════

def inject_user_model(ctx: JudgmentContext) -> JudgmentContext:
    """
    补全 Self-Model 层。

    inject_unified_profile 已完成三路汇聚（inject 3）。
    本 injector 补充：
      - 矛盾标记写入 skipped_dimensions
      - 确保 unified_context 文本存在（向后兼容）

    如果 inject_unified_profile 已设置 ctx._profile_entries，直接使用。
    """
    if getattr(ctx, '_profile_entries', None):
        # inject_unified_profile 已完成汇聚，直接补充 skipped_dimensions
        ctx_uc = getattr(ctx, '_unified_context_obj', None)
        if ctx_uc and ctx_uc.contradictions:
            ctx.skipped_dimensions = getattr(ctx, 'skipped_dimensions', [])
            for c_ in ctx_uc.contradictions:
                ctx.skipped_dimensions.append(
                    "contradiction:{} vs {}".format(c_.l1_claim[:30], c_.l2_behavior[:30])
                )
        # 确保 unified_context 文本存在
        if not getattr(ctx, 'unified_context', ''):
            ctx.unified_context = "[User Profile] data loaded"
        return ctx

    # 兜底：独立运行（正常不会走到这里）
    try:
        from .user_model import UserModel
        um = UserModel(user_id=ctx.user_id)
        ctx_uc = um.get_context_for_task(ctx.task_text, ctx.user_id)
        entries = um.generate_profile(ctx_uc, ctx.task_text)
        ctx._profile_entries = entries
        ctx._unified_context_obj = ctx_uc
        ctx.unified_context = um.synthesize(ctx_uc, ctx.task_text)
        ctx.skipped_dimensions = []
        for c_ in ctx_uc.contradictions:
            ctx.skipped_dimensions.append(
                "contradiction:{} vs {}".format(c_.l1_claim[:30], c_.l2_behavior[:30])
            )
    except Exception:
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

def check10d_full(task_text: str, config: dict = None, user_id: str = "default") -> dict:
    """
    全量 pipeline 判断（供 MCP server 等外部调用）。

    流程：
        0. IntentRouter.route() — 判断是否需要 check10d
        1. prefetch() — 预取 biography/experiences/emotion/self_model
        2. run_pipeline() — 注入全部上下文
        3. 返回完整结果（verdict + dimensions + confidence + chain_id）

    Args:
        task_text: 判断问题
        config: 可选配置（目前未使用，保留接口兼容）
        user_id: 用户标识，用于多用户数据隔离

    Returns:
        dict，含 verdict/confidence/chain_id/dimensions
    """
    # [ZeusHammer IntentRouter] 80% 简单任务不走 LLM 判断
    try:
        from judgment.intent_router import route, handle, direct_reply, IntentType
        ir = route(task_text)
        if not ir.should_check10d:
            reply = direct_reply(ir.intent_type, task_text)
            return {
                "task": task_text,
                "verdict": reply or f"[{ir.intent_type.value}]",
                "confidence": ir.confidence,
                "chain_id": "",
                "dimensions": [],
                "intent_type": ir.intent_type.value,
                "should_check10d": False,
                "note": ir.note,
            }
    except Exception:
        pass  # 降级：正常走 check10d_run

    from judgment.router import check10d_run
    return check10d_run(task_text, user_id=user_id)


def check10d_quick(task_text: str, user_id: str = "default", timeout: float = 50.0) -> dict:
    """
    快速判断（simple 复杂度，50s 超时兜底）。
    用于 CLI / Hermes QQ 触发等非阻塞场景。
    
    Args:
        task_text: 判断问题
        user_id: 用户标识
        timeout: 超时秒数（默认50s），超时则返回 error verdict
    
    Returns:
        dict，含 verdict/confidence/chain_id/dimensions
    """
    import signal
    from judgment.router import check10d_run

    def _timeout_handler(signum, frame):
        raise TimeoutError("check10d_quick timeout")

    # 先尝试 IntentRouter（不占 timeout）
    try:
        from judgment.intent_router import route, direct_reply, IntentType
        ir = route(task_text)
        if not ir.should_check10d:
            reply = direct_reply(ir.intent_type, task_text)
            return {
                "task": task_text,
                "verdict": reply or f"[{ir.intent_type.value}]",
                "confidence": ir.confidence,
                "chain_id": "",
                "dimensions": [],
                "intent_type": ir.intent_type.value,
                "should_check10d": False,
                "note": ir.note,
            }
    except Exception:
        pass  # 降级：正常走 check10d_run

    # 安装超时（signal只在主线程有效，改用子进程方案）
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(check10d_run, task_text, None, None, user_id, "simple")
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return {
                "task": task_text,
                "verdict": "⚠️ 判断超时（30s），建议简化问题或稍后再试",
                "confidence": 0.0,
                "chain_id": "",
                "dimensions": [],
                "error": "timeout",
            }


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

    注入顺序：
      1. inject_emotion        — 情绪 PAD 调制
      2. inject_unified_profile — 三路合一汇聚（L1+L2+L3+矛盾+时间衰减）
      3. inject_self_model     — 动态权重 prior_adjustments
      4. inject_user_model     — 补全矛盾标记 + 向后兼容

    注意：三个旧injector(inject_biography/inject_experiences/inject_correlation_memory)
          已物理删除，仅通过 inject_unified_profile 调用。
    """
    ctx = inject_emotion(ctx)
    ctx = inject_unified_profile(ctx)   # 单一汇聚：三路 + 矛盾 + 时间衰减
    ctx = inject_self_model(ctx)
    ctx = inject_user_model(ctx)        # 补全：矛盾标记 + 向后兼容
    return ctx
