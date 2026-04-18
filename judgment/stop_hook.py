# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/stop_hook.py  →  NEW: subsystems/judgment/stop_hook.py
from subsystems.judgment.stop_hook import (
    EventType, Instinct, Trajectory, StopHook,
    get_stop_hook, capture_judgment, capture_verdict, capture_tool_call,
    finalize_session, init_instinct_db, get_instincts, promote_instinct,
)
