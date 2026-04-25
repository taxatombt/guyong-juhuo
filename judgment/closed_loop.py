# judgment/closed_loop.py
# Shim: subsystems/judgment/closed_loop re-export
from subsystems.judgment.closed_loop import (
    init,
    snapshot_judgment, receive_verdict, record_judgment,
    verify_outcome, get_recent_chains, get_dimension_beliefs,
    start_verdict_listener, stop_verdict_listener, is_listener_active,
    get_prior_adjustments,
    predict_outcome, get_verification_stats, auto_predict_from_verdict,
    _get_db_conn,
)
