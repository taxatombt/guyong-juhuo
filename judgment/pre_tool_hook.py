# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/pre_tool_hook.py  →  NEW: subsystems/judgment/pre_tool_hook.py
from subsystems.judgment.pre_tool_hook import (
    HookAction, PreToolUseRequest, PreToolUseOutcome, PreToolHook,
    PostToolUseResult, PostToolHook,
)
