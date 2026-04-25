# judgment/self_evolver.py
# Shim: subsystems/judgment/self_evolver re-export
from subsystems.judgment.self_evolver import (
    get_conn, sync_to_self_model, check_trigger, get_cases,
    compute_new_weights, compare, apply_evolved_weights,
    run_evolution_cycle, EvolverScheduler,
    get_scheduler, start_evolver_scheduler,
)
