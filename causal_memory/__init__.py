# causal_memory/__init__.py — Lazy-loading Shim
# router.py: from causal_memory import recall_causal_history, inject_to_judgment_input, find_similar_events, init
# cli.py: from causal_memory.causal_chain import get_recent_chains, get_chain_detail
from .causal_memory import (
    init,
    load_all_events,
    load_all_links,
    record_event,
    log_causal_event,
    add_causal_link,
    capture_causal_link,
    find_similar_events,
    recall_causal_history,
    inject_to_judgment_input,
    get_links_needing_revalidation,
    scan_low_quality_links,
    suggest_evolution,
    get_stats,
    get_statistics,
    update_link_quality_for_event,
    fix_causal_link,
    check_and_trigger_self_model_update,
)
from .causal_chain import (
    build_causal_chain,
    format_causal_report,
    get_recent_chains,
    get_chain_detail,
)
from subsystems.judgment.closed_loop import get_recent_chains as _grc_closed_loop


# CausalMemoryCompat — 让 router.py 的 `causal_memory.recall_causal_history(task)` 语法工作
class _CausalMemoryCompat:
    def recall_causal_history(self, task):
        return recall_causal_history(task)
    def inject_to_judgment_input(self, task):
        return inject_to_judgment_input(task)
    def find_similar_events(self, task, max_results=3):
        return find_similar_events(task, max_results)
    def init(self):
        return init()

causal_memory = _CausalMemoryCompat()

# ── Lazy-load causal_inference（触发 llm_adapter/SSL，不在顶层导入）────────
_LAZY = {
    "CausalInferenceEngine": (".causal_inference", "CausalInferenceEngine"),
    "infer_causal_chain": (".causal_inference", "infer_causal_chain"),
}

def __getattr__(name):
    if name in _LAZY:
        mod_path, attr = _LAZY[name]
        from importlib import import_module
        mod = import_module(mod_path, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module 'causal_memory' has no attribute '{name}'")

__all__ = [
    "init", "recall_causal_history", "inject_to_judgment_input",
    "find_similar_events", "record_event", "log_causal_event",
    "add_causal_link", "capture_causal_link", "get_recent_chains",
    "get_stats", "get_statistics",
    "build_causal_chain", "format_causal_report",
    "causal_memory",
    "get_chain_detail",
]
