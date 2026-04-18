# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/self_evolover.py  →  NEW: subsystems/judgment/self_evolover.py
from subsystems.judgment.self_evolover import (
    sync_to_self_model, check_trigger,
    get_cases, compute_new_weights, compare, apply_evolved_weights,
    run_evolution_cycle,
    get_scheduler, start_evolver_scheduler, EvolverScheduler,
)
