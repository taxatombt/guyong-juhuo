# subsystems/judgment/ — 十维判断子系统（canonical location）
# 使用 __getattr__ 懒加载，避免顶层 import 触发 llm_adapter/ssl 链
from sys import modules as _sys_modules

# 顶层导出（无副作用的轻量模块）
from .dimensions import DIMENSIONS, Dimension
from .confidence import (
    DimensionConfidence,
    calculate_dimension_confidence,
    calculate_average_confidence,
    get_low_confidence_dimensions,
)
from .dynamic_weights import (
    WeightConfig,
    get_dynamic_weights,
    get_task_complexity,
    detect_task_types,
)
from .judgment_path import JudgmentPath
from .metacognitive import (
    metacognitive_review,
    metacognitive_self_check,
    get_bias_checklist,
)
from .protocol import ExitCode, JudgmentMessage, JudgmentResult
from .matcher import MatchLevel, MatchResult, Matcher, MatcherRule
from .closed_loop import (
    init, snapshot_judgment, receive_verdict,
    get_prior_adjustments, get_recent_chains, get_dimension_beliefs,
    start_verdict_listener, stop_verdict_listener, is_listener_active,
    record_judgment, predict_outcome, verify_outcome,
    get_verification_stats, auto_predict_from_verdict,
)

# 以下用 __getattr__ 懒加载（避免触发 SSL/llm_adapter）
_LAZY_MAP = {
    # Phase 2
    "get_conn": ("judgment_db", "get_conn"),
    "init_db": ("judgment_db", "init_db"),
    "save_judgment": ("judgment_db", "save_judgment"),
    "save_verdict": ("judgment_db", "save_verdict"),
    "update_dimension_stats": ("judgment_db", "update_dimension_stats"),
    "get_judgment": ("judgment_db", "get_judgment"),
    "get_recent_judgments": ("judgment_db", "get_recent_judgments"),
    "get_dimension_stats": ("judgment_db", "get_dimension_stats"),
    "get_overall_accuracy": ("judgment_db", "get_overall_accuracy"),
    "get_verdict_history": ("judgment_db", "get_verdict_history"),
    "get_stats": ("judgment_db", "get_stats"),
    "migrate_from_json": ("judgment_db", "migrate_from_json"),
    # fitness
    "JP": ("fitness_baseline", "JP"),
    "FitnessBaseline": ("fitness_baseline", "FitnessBaseline"),
    "DimensionAccuracy": ("fitness_evolution", "DimensionAccuracy"),
    "FitnessEvolution": ("fitness_evolution", "FitnessEvolution"),
    "get_fitness": ("fitness_evolution", "get_fitness"),
    "record_judgment_outcome": ("fitness_evolution", "record_judgment_outcome"),
    "get_boosted_weights": ("fitness_evolution", "get_boosted_weights"),
    "get_fitness_stats": ("fitness_evolution", "get_fitness_stats"),
    # insight
    "ET": ("insight_tracker", "ET"),
    "Event": ("insight_tracker", "Event"),
    "InsightTracker": ("insight_tracker", "InsightTracker"),
    "insight_tracker": ("insight_tracker", "insight_tracker"),
    # verdict
    "VerdictRecord": ("verdict_collector", "VerdictRecord"),
    "ensure_dir": ("verdict_collector", "ensure_dir"),
    "load_verdicts": ("verdict_collector", "load_verdicts"),
    "count_verdicts": ("verdict_collector", "count_verdicts"),
    "is_ready_for_evolution": ("verdict_collector", "is_ready_for_evolution"),
    "get_collection_status": ("verdict_collector", "get_collection_status"),
    "import_from_judgment_db": ("verdict_collector", "import_from_judgment_db"),
    "run_full_collection": ("verdict_collector", "run_full_collection"),
    "auto_collect": ("verdict_collector", "auto_collect"),
    # benchmark（触发 llm_adapter）
    "Benchmark": ("benchmark", "Benchmark"),
    "BenchmarkCase": ("benchmark", "BenchmarkCase"),
    "BenchmarkResult": ("benchmark", "BenchmarkResult"),
    "BenchmarkReport": ("benchmark", "BenchmarkReport"),
    "run_benchmark": ("benchmark", "run_benchmark"),
    # verifier（触发 llm_adapter）
    "JudgmentVerifier": ("verifier", "JudgmentVerifier"),
    "verify_judgment": ("verifier", "verify_judgment"),
    # rules
    "RuleResult": ("judgment_rules", "RuleResult"),
    "BaseRule": ("judgment_rules", "BaseRule"),
    "CognitiveRule": ("judgment_rules", "CognitiveRule"),
    "GameTheoryRule": ("judgment_rules", "GameTheoryRule"),
    "EconomicRule": ("judgment_rules", "EconomicRule"),
    "DialecticalRule": ("judgment_rules", "DialecticalRule"),
    "EmotionalRule": ("judgment_rules", "EmotionalRule"),
    "IntuitiveRule": ("judgment_rules", "IntuitiveRule"),
    "MoralRule": ("judgment_rules", "MoralRule"),
    "SocialRule": ("judgment_rules", "SocialRule"),
    "TemporalRule": ("judgment_rules", "TemporalRule"),
    "MetacognitiveRule": ("judgment_rules", "MetacognitiveRule"),
    "evaluate_all_rules": ("judgment_rules", "evaluate_all_rules"),
    "get_llm_required_dimensions": ("judgment_rules", "get_llm_required_dimensions"),
    "get_rule_scores": ("judgment_rules", "get_rule_scores"),
    "rule_based_precheck": ("judgment_rules", "rule_based_precheck"),
    # context
    "FenceContext": ("context_fence", "FenceContext"),
    "ContextFence": ("context_fence", "ContextFence"),
    "get_fence": ("context_fence", "get_fence"),
    "wrap_context": ("context_fence", "wrap_context"),
    "build_judgment_context": ("context_fence", "build_judgment_context"),
    "scan_threats": ("context_fence", "scan_threats"),
    # self_review
    "LessonRecord": ("self_review", "LessonRecord"),
    "PatternAlert": ("self_review", "PatternAlert"),
    "SelfReviewSystem": ("self_review", "SelfReviewSystem"),
    "detect_task_dimensions": ("self_review", "detect_task_dimensions"),
    # life_cycle
    "HookContext": ("life_cycle_hooks", "HookContext"),
    "DelegationResult": ("life_cycle_hooks", "DelegationResult"),
    "LifeCycleHooks": ("life_cycle_hooks", "LifeCycleHooks"),
    "init_hook_db": ("life_cycle_hooks", "init_hook_db"),
    "get_lifecycle_hooks": ("life_cycle_hooks", "get_lifecycle_hooks"),
    "build_system_prompt": ("life_cycle_hooks", "build_system_prompt"),
    "prefetch_all": ("life_cycle_hooks", "prefetch_all"),
    "on_turn_start": ("life_cycle_hooks", "on_turn_start"),
    "on_session_end": ("life_cycle_hooks", "on_session_end"),
    "on_delegation": ("life_cycle_hooks", "on_delegation"),
    "on_pre_action": ("life_cycle_hooks", "on_pre_action"),
    "on_post_action": ("life_cycle_hooks", "on_post_action"),
    # stop_hook
    "EventType": ("stop_hook", "EventType"),
    "Instinct": ("stop_hook", "Instinct"),
    "Trajectory": ("stop_hook", "Trajectory"),
    "StopHook": ("stop_hook", "StopHook"),
    "get_stop_hook": ("stop_hook", "get_stop_hook"),
    "capture_judgment": ("stop_hook", "capture_judgment"),
    "capture_verdict": ("stop_hook", "capture_verdict"),
    "capture_tool_call": ("stop_hook", "capture_tool_call"),
    "finalize_session": ("stop_hook", "finalize_session"),
    "init_instinct_db": ("stop_hook", "init_instinct_db"),
    "get_instincts": ("stop_hook", "get_instincts"),
    "promote_instinct": ("stop_hook", "promote_instinct"),
    # pre_tool_hook
    "HookAction": ("pre_tool_hook", "HookAction"),
    "PreToolUseRequest": ("pre_tool_hook", "PreToolUseRequest"),
    "PreToolUseOutcome": ("pre_tool_hook", "PreToolUseOutcome"),
    "PreToolHook": ("pre_tool_hook", "PreToolHook"),
    "PostToolUseResult": ("pre_tool_hook", "PostToolUseResult"),
    "PostToolHook": ("pre_tool_hook", "PostToolHook"),
    # self_evolver（触发 llm_adapter）
    "EvolverScheduler": ("self_evolver", "EvolverScheduler"),
    "check_trigger": ("self_evolver", "check_trigger"),
    "compare": ("self_evolver", "compare"),
    "compute_new_weights": ("self_evolver", "compute_new_weights"),
    "run_evolution_cycle": ("self_evolver", "run_evolution_cycle"),
    "start_evolver_scheduler": ("self_evolver", "start_evolver_scheduler"),
    "apply_evolved_weights": ("self_evolver", "apply_evolved_weights"),
    "sync_to_self_model": ("self_evolver", "sync_to_self_model"),
    "main": ("self_evolver", "main"),
    # router/pipeline（触发 llm_adapter）
    "router": ("router", None),
    "pipeline": ("pipeline", None),
}


def __getattr__(name):
    if name in _LAZY_MAP:
        mod_name, attr_name = _LAZY_MAP[name]
        if attr_name is None:
            # 懒加载子模块
            from . import router as _router_mod
            return _router_mod
        mod = __import__(f"subsystems.judgment.{mod_name}", fromlist=[attr_name])
        return getattr(mod, attr_name)
    raise AttributeError(f"module 'subsystems.judgment' has no attribute '{name}'")