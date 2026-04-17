#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_adapter base — 大模型适配器基类

集成 QwenPaw LLM 限流 + Retry 系统
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict
import json

from judgment.logging_config import get_logger
log = get_logger("juhuo.llm_base")

# 可选导入限流器（如果安装了）
try:
    from llm_adapter.rate_limiter import (
        get_rate_limiter, get_concurrency_limiter,
        RetryConfig, with_retry, RetryError,
        LLM_MAX_CONCURRENT, LLM_MAX_QPM,
        LLM_MAX_RETRIES, LLM_BACKOFF_BASE, LLM_BACKOFF_CAP,
    )
    HAS_RATE_LIMITER = True
except ImportError:
    HAS_RATE_LIMITER = False
    log.warning("Rate limiter not available")


@dataclass
class CompletionRequest:
    """统一补全请求"""
    prompt: str
    max_tokens: int = 2000
    temperature: float = 0.7
    top_p: float = 0.95
    stream: bool = False
    stop: Optional[List[str]] = None


@dataclass
class LLMResponse:
    """统一响应"""
    success: bool
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


@dataclass
class KnowledgeUnit:
    """知识单元"""
    name: str
    content: str
    category: str  # CORE_IDENTITY / SELF_MODEL / CAUSAL_MEMORY / JUDGMENT_RULE / GENERAL_SKILL
    confidence: float
    source: str


class LLMAdapter(ABC):
    """大模型适配器基类"""
    
    def __init__(self):
        self._rate_limiter = None
        self._concurrency = None
        if HAS_RATE_LIMITER:
            self._rate_limiter = get_rate_limiter()
            self._concurrency = get_concurrency_limiter()
    
    @abstractmethod
    def _complete_impl(self, request: CompletionRequest) -> LLMResponse:
        """实际实现，由子类提供"""
        pass
    
    def complete(self, request: CompletionRequest) -> LLMResponse:
        """
        带限流和重试的 complete
        
        自动处理：
        - QPM 限流
        - 并发控制
        - 429 / 超时重试
        """
        if not HAS_RATE_LIMITER:
            return self._complete_impl(request)
        
        # 限流获取
        import asyncio
        loop = asyncio.get_event_loop()
        
        try:
            # 检查限流
            if not loop.run_until_complete(self._rate_limiter.acquire()):
                log.warning("Rate limit timeout")
                return LLMResponse(False, "", error="Rate limit timeout")
            
            # 并发控制
            if not loop.run_until_complete(self._concurrency.acquire()):
                log.warning("Concurrency limit reached")
                return LLMResponse(False, "", error="Concurrency limit reached")
            
            try:
                # 带重试的调用
                retry_cfg = RetryConfig(
                    max_retries=LLM_MAX_RETRIES,
                    backoff_base=LLM_BACKOFF_BASE,
                    backoff_cap=LLM_BACKOFF_CAP,
                )
                return loop.run_until_complete(
                    with_retry(self._complete_impl, request, config=retry_cfg)
                )
            finally:
                self._concurrency.release()
        
        except RetryError as e:
            log.error(f"Retry exhausted: {e}")
            return LLMResponse(False, "", error=str(e))
        except Exception as e:
            log.error(f"LLM call failed: {e}")
            return LLMResponse(False, "", error=str(e))
    
    def extract_knowledge(self, text: str, source: str) -> List[KnowledgeUnit]:
        """从文本提取知识单元"""
        prompt = f"""从以下文本提取知识单元（JSON数组）：
- name: 名称
- content: 内容  
- category: CORE_IDENTITY/SELF_MODEL/JUDGMENT_RULE/GENERAL_SKILL
- confidence: 0-1

文本：{text[:8000]}
来源：{source}"""
        
        response = self.complete(CompletionRequest(prompt=prompt, temperature=0.3, max_tokens=2000))
        if not response.success:
            return []
        
        try:
            start = response.content.find('[')
            end = response.content.rfind(']')
            if start >= 0:
                data = json.loads(response.content[start:end+1])
                return [KnowledgeUnit(
                    name=i.get('name', 'unnamed'),
                    content=i.get('content', ''),
                    category=i.get('category', 'GENERAL_SKILL'),
                    confidence=float(i.get('confidence', 0.8)),
                    source=source,
                ) for i in data]
        except:
            pass
        
        return [KnowledgeUnit("extracted", response.content, "GENERAL_SKILL", 0.5, source)]
    
    def suggest_evolution(self, current: str, records: str) -> Optional[str]:
        """基于执行记录建议进化"""
        prompt = f"""当前技能：\n{current}\n\n执行记录：\n{records}\n\n改进建议（只输出改进后的内容）："""
        response = self.complete(CompletionRequest(prompt=prompt, temperature=0.5, max_tokens=2000))
        return response.content.strip() if response.success else None
