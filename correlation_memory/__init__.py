# correlation_memory/__init__.py — Lazy-loading Shim
# router.py: from correlation_memory import recall_correlation_history, inject_to_judgment_input, find_similar_events, init
# cli.py: from correlation_memory.correlation_chain import get_recent_chains, get_chain_detail
from .correlation_memory import (
    init,
    load_all_events,
    load_all_links,
    record_event,
    log_correlation_event,
    add_correlation_link,
    capture_correlation_link,
    find_similar_events,
    recall_correlation_history,
    inject_to_judgment_input,
    get_links_needing_revalidation,
    scan_low_quality_links,
    suggest_evolution,
    get_stats,
    get_statistics,
    update_link_quality_for_event,
    fix_correlation_link,
    check_and_trigger_self_model_update,
)
from .correlation_chain import (
    build_causal_chain,
    format_causal_report,
    get_recent_chains,
    get_chain_detail,
)
from subsystems.judgment.closed_loop import get_recent_chains as _grc_closed_loop


# _CorrelationMemoryCompat — 同时支持旧名（向后兼容）
class _CorrelationMemoryCompat:
    def recall_correlation_history(self, task):
        return recall_correlation_history(task)
    def recall_causal_history(self, task):
        """向后兼容别名"""
        return recall_correlation_history(task)
    def inject_to_judgment_input(self, task):
        return inject_to_judgment_input(task)
    def find_similar_events(self, task, max_results=3):
        return find_similar_events(task, max_results)
    def init(self):
        return init()

correlation_memory = _CorrelationMemoryCompat()

# ── Lazy-load correlation_inference（触发 llm_adapter/SSL，不在顶层导入）────────
_LAZY = {
    "CorrelationInferenceEngine": (".correlation_inference", "CorrelationInferenceEngine"),
    "infer_correlation_chain": (".correlation_inference", "infer_correlation_chain"),
    # 向后兼容别名
    "CausalInferenceEngine": (".correlation_inference", "CorrelationInferenceEngine"),
    "infer_causal_chain": (".correlation_inference", "infer_correlation_chain"),
}

def __getattr__(name):
    if name in _LAZY:
        mod_path, attr = _LAZY[name]
        from importlib import import_module
        mod = import_module(mod_path, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module 'correlation_memory' has no attribute '{name}'")

__all__ = [
    "init", "recall_correlation_history", "inject_to_judgment_input",
    "find_similar_events", "record_event", "log_correlation_event",
    "add_correlation_link", "capture_correlation_link", "get_recent_chains",
    "get_stats", "get_statistics",
    "build_causal_chain", "format_causal_report",
    "correlation_memory",
    "get_chain_detail",
]
