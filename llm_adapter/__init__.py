# Shim: re-export from canonical new location
# Migration: 2026-04-18
# OLD: llm_adapter/*  →  NEW: adapters/llm/*
from adapters.llm import (
    LLMAdapter, LLMResponse, CompletionRequest,
    MiniMaxAdapter, OpenAIAdapter, OllamaAdapter,
    load_config, get_adapter,
)
from adapters.llm.base import KnowledgeUnit


# ollama fallback
from llm_adapter.ollama_fallback import (
    FallbackRouter,
    OllamaClient,
    OllamaConfig,
    OllamaUnavailableError,
    OllamaCallError,
    get_fallback_router,
    ollama_status,
    ollama_wrap,
)
__all__ = [
    'LLMAdapter', 'LLMResponse', 'CompletionRequest', 'KnowledgeUnit',
    'MiniMaxAdapter', 'OpenAIAdapter', 'OllamaAdapter',
    'load_config', 'get_adapter',
]
