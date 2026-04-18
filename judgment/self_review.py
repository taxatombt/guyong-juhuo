# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/self_review.py  →  NEW: subsystems/judgment/self_review.py
from subsystems.judgment.self_review import (
    LessonRecord, PatternAlert, SelfReviewSystem,
    detect_task_dimensions,
)
