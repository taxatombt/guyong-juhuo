# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: evolver/verdict_collector.py  →  NEW: subsystems/judgment/verdict_collector.py
# Note: evolver/ is also a top-level module, so the shim stays in evolver/
from subsystems.judgment.verdict_collector import (
    VerdictRecord,
    ensure_dir, save_verdict, load_verdicts, count_verdicts,
    is_ready_for_evolution, get_collection_status,
    import_from_judgment_db, run_full_collection, auto_collect,
)
