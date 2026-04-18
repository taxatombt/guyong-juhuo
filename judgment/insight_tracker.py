# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/insight_tracker.py  →  NEW: subsystems/judgment/insight_tracker.py
from subsystems.judgment.insight_tracker import (
    ET, Event, InsightTracker,
    insight_tracker,
)
