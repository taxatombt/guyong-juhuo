# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/closed_loop.py  →  NEW: subsystems/judgment/closed_loop.py
from subsystems.judgment.closed_loop import (
    init, snapshot_judgment, receive_verdict,
    get_prior_adjustments, get_recent_chains, get_dimension_beliefs,
    start_verdict_listener, stop_verdict_listener, is_listener_active,
    record_judgment, predict_outcome, verify_outcome,
    get_verification_stats, auto_predict_from_verdict,
)
