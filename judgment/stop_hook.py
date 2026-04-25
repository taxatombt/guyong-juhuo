# judgment/stop_hook.py
# Shim: subsystems/judgment/stop_hook re-export
from subsystems.judgment.stop_hook import (
    StopHook, EventType, Trajectory, Instinct,
    get_stop_hook,
    capture_judgment, capture_verdict, capture_tool_call,
    finalize_session,
    init_instinct_db, get_instincts, promote_instinct,
)
