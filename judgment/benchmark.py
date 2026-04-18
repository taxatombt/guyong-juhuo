# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: judgment/benchmark.py  →  NEW: subsystems/judgment/benchmark.py
from subsystems.judgment.benchmark import (
    Benchmark, BenchmarkCase, BenchmarkResult, BenchmarkReport,
    run_benchmark,
)
