# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: llm_adapter/minimax.py  →  NEW: adapters/llm/minimax.py
from adapters.llm.minimax import MiniMaxAdapter
from adapters.llm import get_adapter
