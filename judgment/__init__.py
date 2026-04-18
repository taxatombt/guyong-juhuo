# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/*  →  NEW: subsystems/judgment/*
# 已迁移: dimensions
from subsystems.judgment.dimensions import DIMENSIONS, Dimension

# 以下尚未迁移，保持原导入路径
from .router import check10d, route, format_report, format_structured
from .closed_loop import (
    snapshot_judgment,
    receive_verdict,
    predict_outcome,
    verify_outcome,
    get_verification_stats,
    get_dimension_beliefs,
    get_recent_chains,
)
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
from .verifier import JudgmentVerifier, verify_judgment

__all__ = [
    'check10d', 'route', 'format_report', 'format_structured',
    'snapshot_judgment', 'receive_verdict', 'predict_outcome',
    'verify_outcome', 'get_verification_stats', 'get_dimension_beliefs',
    'get_recent_chains',
    'DIMENSIONS', 'Dimension',
    'DimensionConfidence', 'calculate_dimension_confidence',
    'calculate_average_confidence', 'get_low_confidence_dimensions',
    'WeightConfig', 'get_dynamic_weights', 'get_task_complexity',
    'detect_task_types',
    'JudgmentPath',
    'metacognitive_review', 'metacognitive_self_check', 'get_bias_checklist',
    'JudgmentVerifier', 'verify_judgment',
]
