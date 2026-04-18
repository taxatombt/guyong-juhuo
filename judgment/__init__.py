# judgment/ — 懒加载入口 (re-export 已迁移内容)
# Migration: 2026-04-18 Phase 1-5
# 
# 问题: subsystems/judgment/*.py 里的 "from judgment.x" 会触发本文件执行，
#       而本文件顶层导入 subsystems.judgment 时，subsystems.judgment 还在初始化中。
# 修复: 用 __getattr__ 懒加载 subsystems.judgment 的导出，模块加载时不做任何导入。
#       注意: .router 和 .pipeline 是本目录的 shim，可以安全地顶层导入。
import sys as _sys

# 本地 shim 文件（可安全顶层导入）
from .router import check10d, route, format_report, format_structured
from .pipeline import check10d_full

# subsystems.judgment 的导出用 __getattr__ 懒加载（避免顶层循环导入）
_SUBSYSTEMS_EXPORTS = [
    "DIMENSIONS", "Dimension",
    "ExitCode", "JudgmentMessage", "JudgmentResult",
    "MatchLevel", "MatchResult", "Matcher", "MatcherRule",
    "DimensionConfidence", "calculate_dimension_confidence",
    "calculate_average_confidence", "get_low_confidence_dimensions",
    "WeightConfig", "get_dynamic_weights", "get_task_complexity", "detect_task_types",
    "JudgmentPath",
    "metacognitive_review", "metacognitive_self_check", "get_bias_checklist",
    "Benchmark", "run_benchmark",
    "JudgmentVerifier", "verify_judgment",
    "JP", "FitnessBaseline",
    "FitnessEvolution", "get_fitness", "record_judgment_outcome",
    "get_boosted_weights", "get_fitness_stats",
    "ET", "Event", "InsightTracker", "insight_tracker",
    "VerdictRecord", "ensure_dir", "save_verdict", "load_verdicts", "count_verdicts",
    "is_ready_for_evolution", "get_collection_status", "import_from_judgment_db",
    "run_full_collection", "auto_collect",
    "get_conn", "init_db", "save_judgment", "update_dimension_stats",
    "get_judgment", "get_recent_judgments", "get_dimension_stats",
    "get_overall_accuracy", "get_verdict_history", "get_stats", "migrate_from_json",
    "RuleResult", "BaseRule", "CognitiveRule", "GameTheoryRule", "EconomicRule",
    "DialecticalRule", "EmotionalRule", "IntuitiveRule", "MoralRule",
    "SocialRule", "TemporalRule", "MetacognitiveRule",
    "evaluate_all_rules", "get_llm_required_dimensions", "get_rule_scores",
    "rule_based_precheck",
    "FenceContext", "ContextFence", "get_fence", "wrap_context",
    "build_judgment_context", "scan_threats",
    "LessonRecord", "PatternAlert", "SelfReviewSystem", "detect_task_dimensions",
    "HookContext", "DelegationResult", "LifeCycleHooks",
    "init_hook_db", "get_lifecycle_hooks", "build_system_prompt",
    "prefetch_all", "on_turn_start", "on_session_end",
    "on_delegation", "on_pre_action", "on_post_action",
    "EventType", "Instinct", "Trajectory", "StopHook",
    "get_stop_hook", "capture_judgment", "capture_verdict", "capture_tool_call",
    "finalize_session", "init_instinct_db", "get_instincts", "promote_instinct",
    "init", "snapshot_judgment", "receive_verdict",
    "get_prior_adjustments", "get_recent_chains", "get_dimension_beliefs",
    "start_verdict_listener", "stop_verdict_listener", "is_listener_active",
    "record_judgment", "predict_outcome", "verify_outcome",
    "get_verification_stats", "auto_predict_from_verdict",
    "sync_to_self_model", "check_trigger", "get_cases", "compute_new_weights",
    "compare", "apply_evolved_weights", "run_evolution_cycle",
    "get_scheduler", "start_evolver_scheduler", "EvolverScheduler",
    "DATA_DIR", "EVOLUTIONS_DIR", "JUDGMENT_DATA_DIR", "CONFIG_FILE",
    "EvolverConfig", "BenchmarkConfig", "LLMConfig", "JudgmentConfig",
    "load_config", "save_config", "get_evolver", "get_benchmark", "get_llm",
    "BIAS_THRESHOLD", "BIAS_CONSECUTIVE", "ACCURACY_THRESHOLD",
    "MIN_SAMPLES", "COOLDOWN_HOURS", "VALIDATION_WINDOW",
    "ACCURACY_IMPROVEMENT_THRESHOLD", "MIN_VERDICTS_FOR_EVOLUTION",
    "setup_logging",
]

_subsystems_mod = None

def _get_subsystems():
    global _subsystems_mod
    if _subsystems_mod is None:
        from subsystems import judgment as _subsystems_mod
    return _subsystems_mod

def __getattr__(name):
    if name in _SUBSYSTEMS_EXPORTS:
        return getattr(_get_subsystems(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return list(globals().keys()) + _SUBSYSTEMS_EXPORTS
