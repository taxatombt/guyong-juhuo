# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/fitness_evolution.py  →  NEW: subsystems/judgment/fitness_evolution.py
from subsystems.judgment.fitness_evolution import (
    DimensionAccuracy, FitnessEvolution,
    get_fitness, record_judgment_outcome, get_boosted_weights, get_fitness_stats,
)
