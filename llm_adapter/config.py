# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: llm_adapter/config.py  →  NEW: adapters/llm/config.py
from adapters.llm.config import load_config, get_adapter
