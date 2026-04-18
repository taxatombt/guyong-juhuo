# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/config.py  →  NEW: subsystems/judgment/config.py
from subsystems.judgment.config import (
    DATA_DIR, EVOLUTIONS_DIR, JUDGMENT_DATA_DIR, CONFIG_FILE,
    EvolverConfig, BenchmarkConfig, LLMConfig, JudgmentConfig,
    load_config, save_config, get_evolver, get_benchmark, get_llm,
    BIAS_THRESHOLD, BIAS_CONSECUTIVE, ACCURACY_THRESHOLD,
    MIN_SAMPLES, COOLDOWN_HOURS, VALIDATION_WINDOW,
    ACCURACY_IMPROVEMENT_THRESHOLD, MIN_VERDICTS_FOR_EVOLUTION,
)
