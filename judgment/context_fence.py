# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/context_fence.py  →  NEW: subsystems/judgment/context_fence.py
from subsystems.judgment.context_fence import (
    FenceContext, ContextFence,
    get_fence, wrap_context, build_judgment_context, scan_threats,
)
