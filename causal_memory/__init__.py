from .causal_memory import (
    init,
    log_causal_event,
    find_similar_events,
    load_all_events,
    load_all_links,
    add_causal_link,
    recall_causal_history,
    inject_to_judgment_input,
    infer_daily_causal_chains,
    fix_causal_link,
    derive_causal_link,
    capture_causal_link,
    suggest_evolution,
    get_links_needing_revalidation,
    get_statistics,
    scan_low_quality_links,
    mark_cascade_revalidation,
    update_link_quality_for_event,
)

from .types import (
    CausalEvent,
    CausalLink,
    CausalLinkQuality,
    CausalRelation,
    EvolutionType,
    EvolutionSuggestion,
    CausalStats,
)

from .diff_tracker import (
    TurnDiffTracker,
    FileChange,
    TurnDiff,
    TRACKER_FILE,
)

__all__ = [
    # 核心功能
    "init",
    "log_causal_event",
    "find_similar_events",
    "load_all_events",
    "load_all_links",
    "add_causal_link",
    "recall_causal_history",
    "inject_to_judgment_input",
    "infer_daily_causal_chains",
    # OpenSpace 启发的三级进化 + 级联更新
    "fix_causal_link",          # FIX: 就地修正
    "derive_causal_link",       # DERIVED: 衍生特定版本
    "capture_causal_link",      # CAPTURED: 捕获全新
    "suggest_evolution",        # 扫描建议进化
    "get_links_needing_revalidation",
    "get_statistics",
    "scan_low_quality_links",   # 低质量扫描（对应 OpenSpace 指标监控）
    "mark_cascade_revalidation", # 级联更新标记（OpenSpace 级联进化）
    "update_link_quality_for_event",
    # 类型
    "CausalEvent",
    "CausalLink",
    "CausalLinkQuality",
    "CausalRelation",
    "EvolutionType",
    "EvolutionSuggestion",
    "CausalStats",
    # TurnDiffTracker（决策影响追踪）
    "TurnDiffTracker",
    "FileChange",
    "TurnDiff",
    "TRACKER_FILE",
]

# 兼容旧名称
record_judgment_event = log_causal_event
