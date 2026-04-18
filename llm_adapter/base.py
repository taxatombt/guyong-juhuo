# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: llm_adapter/base.py  →  NEW: adapters/llm/base.py
from adapters.llm.base import (
    LLMAdapter, LLMResponse, CompletionRequest, KnowledgeUnit,
)
