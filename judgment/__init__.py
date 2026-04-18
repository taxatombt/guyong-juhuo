#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment — 十维判断系统核心模块

十维框架:
  1. 认知维度    — 事实清楚吗？有认知偏差吗？
  2. 博弈维度    — 各方立场和激励是什么？
  3. 经济维度    — 机会成本？投入产出比？
  4. 辩证维度    — 主要矛盾是什么？反方观点？
  5. 情绪维度    — 情绪影响判断吗？情绪PAD打分
  6. 直觉维度    — 第一反应可信吗？
  7. 道德维度    — 符合价值观吗？应不应该？
  8. 社会维度    — 我在做自己还是演别人？
  9. 时间维度    — 时间折扣，五年后怎么看？
  10.元认知维度  — 我有盲区吗？哪里可能错？
"""

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
from .verifier import JudgmentVerifier, verify_judgment

__all__ = [
    'check10d',
    'route',
    'format_report',
    'format_structured',
    'DIMENSIONS',
    'Dimension',
    'DimensionConfidence',
    'calculate_dimension_confidence',
    'calculate_average_confidence',
    'get_low_confidence_dimensions',
    'WeightConfig',
    'get_dynamic_weights',
    'get_task_complexity',
    'detect_task_types',
    'JudgmentPath',
    'metacognitive_review',
    'metacognitive_self_check',
    'get_bias_checklist',
]
