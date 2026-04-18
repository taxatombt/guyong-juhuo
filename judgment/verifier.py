# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/verifier.py  →  NEW: subsystems/judgment/verifier.py
from subsystems.judgment.verifier import (
    JudgmentVerifier, verify_judgment,
)
