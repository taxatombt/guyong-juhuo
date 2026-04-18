# subsystems/judgment/ — 十维判断子系统（canonical location）
# 旧路径 judgment/ 的文件为 shim，逐步迁移到本目录。
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

# Phase 2: closed_loop/benchmark/verifier/fitness chain
from .judgment_db import (
    get_conn, init_db,
    save_judgment, save_verdict, update_dimension_stats,
    get_judgment, get_recent_judgments,
    get_dimension_stats, get_overall_accuracy,
    get_verdict_history, get_stats,
    migrate_from_json,
)
from .fitness_baseline import JP, FitnessBaseline
from .fitness_evolution import (
    DimensionAccuracy, FitnessEvolution,
    get_fitness, record_judgment_outcome,
    get_boosted_weights, get_fitness_stats,
)
from .insight_tracker import ET, Event, InsightTracker, insight_tracker
from .verdict_collector import (
    VerdictRecord,
    ensure_dir, save_verdict, load_verdicts, count_verdicts,
    is_ready_for_evolution, get_collection_status,
    import_from_judgment_db, run_full_collection, auto_collect,
)
from .benchmark import (
    Benchmark, BenchmarkCase, BenchmarkResult, BenchmarkReport,
    run_benchmark,
)
from .verifier import JudgmentVerifier, verify_judgment

# Phase 3: judgment 内联工具迁移
from .judgment_rules import (
    RuleResult, BaseRule, CognitiveRule, GameTheoryRule, EconomicRule,
    DialecticalRule, EmotionalRule, IntuitiveRule, MoralRule,
    SocialRule, TemporalRule, MetacognitiveRule,
    evaluate_all_rules, get_llm_required_dimensions, get_rule_scores, rule_based_precheck,
)
from .context_fence import (
    FenceContext, ContextFence,
    get_fence, wrap_context, build_judgment_context, scan_threats,
)
from .self_review import (
    LessonRecord, PatternAlert, SelfReviewSystem,
    detect_task_dimensions,
)
from .life_cycle_hooks import (
    HookContext, DelegationResult, LifeCycleHooks,
    init_hook_db, get_lifecycle_hooks, build_system_prompt,
    prefetch_all, on_turn_start, on_session_end,
    on_delegation, on_pre_action, on_post_action,
)
from .stop_hook import (
    EventType, Instinct, Trajectory, StopHook,
    get_stop_hook, capture_judgment, capture_verdict, capture_tool_call,
    finalize_session, init_instinct_db, get_instincts, promote_instinct,
)

# Phase 4: pre_tool_hook
from .pre_tool_hook import (
    HookAction, PreToolUseRequest, PreToolUseOutcome, PreToolHook,
    PostToolUseResult, PostToolHook,
)

# Phase 4: closed_loop
from .closed_loop import (
    init, snapshot_judgment, receive_verdict,
    get_prior_adjustments, get_recent_chains, get_dimension_beliefs,
    start_verdict_listener, stop_verdict_listener, is_listener_active,
    record_judgment, predict_outcome, verify_outcome,
    get_verification_stats, auto_predict_from_verdict,
)
from .self_evolover import (
    sync_to_self_model, check_trigger,
    get_cases, compute_new_weights, compare, apply_evolved_weights,
    run_evolution_cycle,
    get_scheduler, start_evolver_scheduler, EvolverScheduler,
)

# config and logging
from .config import (
    DATA_DIR, EVOLUTIONS_DIR, JUDGMENT_DATA_DIR, CONFIG_FILE,
    EvolverConfig, BenchmarkConfig, LLMConfig, JudgmentConfig,
    load_config, save_config, get_evolver, get_benchmark, get_llm,
    BIAS_THRESHOLD, BIAS_CONSECUTIVE, ACCURACY_THRESHOLD,
    MIN_SAMPLES, COOLDOWN_HOURS, VALIDATION_WINDOW,
    ACCURACY_IMPROVEMENT_THRESHOLD, MIN_VERDICTS_FOR_EVOLUTION,
)
from .logging_config import (
    setup_logging, get_logger, info, warning, error, debug,
)

__all__ = [
    # Phase 1
    'DIMENSIONS', 'Dimension',
    'DimensionConfidence', 'calculate_dimension_confidence',
    'calculate_average_confidence', 'get_low_confidence_dimensions',
    'WeightConfig', 'get_dynamic_weights', 'get_task_complexity', 'detect_task_types',
    'JudgmentPath',
    'metacognitive_review', 'metacognitive_self_check', 'get_bias_checklist',
    'ExitCode', 'JudgmentMessage', 'JudgmentResult',
    'MatchLevel', 'MatchResult', 'Matcher', 'MatcherRule',
    # Phase 2
    'get_conn', 'init_db',
    'save_judgment', 'save_verdict', 'update_dimension_stats',
    'get_judgment', 'get_recent_judgments',
    'get_dimension_stats', 'get_overall_accuracy',
    'get_verdict_history', 'get_stats', 'migrate_from_json',
    'JP', 'FitnessBaseline',
    'DimensionAccuracy', 'FitnessEvolution',
    'get_fitness', 'record_judgment_outcome', 'get_boosted_weights', 'get_fitness_stats',
    'ET', 'Event', 'InsightTracker', 'insight_tracker',
    'VerdictRecord',
    'ensure_dir', 'save_verdict', 'load_verdicts', 'count_verdicts',
    'is_ready_for_evolution', 'get_collection_status',
    'import_from_judgment_db', 'run_full_collection', 'auto_collect',
    'Benchmark', 'BenchmarkCase', 'BenchmarkResult', 'BenchmarkReport', 'run_benchmark',
    'JudgmentVerifier', 'verify_judgment',
    # Phase 3
    'RuleResult', 'BaseRule', 'CognitiveRule', 'GameTheoryRule', 'EconomicRule',
    'DialecticalRule', 'EmotionalRule', 'IntuitiveRule', 'MoralRule',
    'SocialRule', 'TemporalRule', 'MetacognitiveRule',
    'evaluate_all_rules', 'get_llm_required_dimensions', 'get_rule_scores', 'rule_based_precheck',
    'FenceContext', 'ContextFence',
    'get_fence', 'wrap_context', 'build_judgment_context', 'scan_threats',
    'LessonRecord', 'PatternAlert', 'SelfReviewSystem', 'detect_task_dimensions',
    'HookContext', 'DelegationResult', 'LifeCycleHooks',
    'init_hook_db', 'get_lifecycle_hooks', 'build_system_prompt',
    'prefetch_all', 'on_turn_start', 'on_session_end',
    'on_delegation', 'on_pre_action', 'on_post_action',
    'EventType', 'Instinct', 'Trajectory', 'StopHook',
    'get_stop_hook', 'capture_judgment', 'capture_verdict', 'capture_tool_call',
    'finalize_session', 'init_instinct_db', 'get_instincts', 'promote_instinct',
    # Phase 4
    'HookAction', 'PreToolUseRequest', 'PreToolUseOutcome', 'PreToolHook',
    'PostToolUseResult', 'PostToolHook',
    # closed_loop
    'init', 'snapshot_judgment', 'receive_verdict',
    'get_prior_adjustments', 'get_recent_chains', 'get_dimension_beliefs',
    'start_verdict_listener', 'stop_verdict_listener', 'is_listener_active',
    'record_judgment', 'predict_outcome', 'verify_outcome',
    'get_verification_stats', 'auto_predict_from_verdict',
    # self_evolover
    'sync_to_self_model', 'check_trigger',
    'get_cases', 'compute_new_weights', 'compare', 'apply_evolved_weights',
    'run_evolution_cycle',
    'get_scheduler', 'start_evolver_scheduler', 'EvolverScheduler',
]
