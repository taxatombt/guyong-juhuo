# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/logging_config.py  →  NEW: subsystems/judgment/logging_config.py
from subsystems.judgment.logging_config import (
    setup_logging, get_logger, info, warning, error, debug,
)
