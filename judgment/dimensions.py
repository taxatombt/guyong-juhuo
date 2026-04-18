# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/dimensions.py  →  NEW: subsystems/judgment/dimensions.py
from subsystems.judgment.dimensions import Dimension, DIMENSIONS

__all__ = ['Dimension', 'DIMENSIONS']
