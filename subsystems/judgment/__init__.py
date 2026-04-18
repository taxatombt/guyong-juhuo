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
]
