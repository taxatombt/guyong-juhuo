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

__all__ = [
    'DIMENSIONS', 'Dimension',
    'DimensionConfidence', 'calculate_dimension_confidence',
    'calculate_average_confidence', 'get_low_confidence_dimensions',
    'WeightConfig', 'get_dynamic_weights', 'get_task_complexity', 'detect_task_types',
    'JudgmentPath',
    'metacognitive_review', 'metacognitive_self_check', 'get_bias_checklist',
    'ExitCode', 'JudgmentMessage', 'JudgmentResult',
    'MatchLevel', 'MatchResult', 'Matcher', 'MatcherRule',
]
