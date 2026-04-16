#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
causal_inference.py — Juhuo 因果推断引擎

P0改进：causal_memory的核心缺失是因果推理，不是存储

核心能力：
1. 给定当前情境 → 推理可能的因果链
2. 收集支持/反对每个假设的证据
3. 评估因果链强度
4. 输出"为什么这个决策是对的"的解释
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass

from llm_adapter.minimax import get_adapter
from llm_adapter.base import CompletionRequest

from .causal_memory import load_all_events, load_all_links, find_similar_events
from .types import CausalRelation


@dataclass
class CausalHypothesis:
    cause: str
    effect: str
    confidence: float
    evidence_for: List[str]
    evidence_against: List[str]
    reasoning: str
    source_events: List[int]


@dataclass
class CausalInferenceResult:
    situation: str
    hypotheses: List[CausalHypothesis]
    best_explanation: str
    reasoning_chain: str
    confidence: float
    needs_more_data: bool


class CausalInferenceEngine:
    """因果推断引擎 - 给judgment提供推理底座"""
    
    def __init__(self):
        self.adapter = get_adapter()
    
    def infer(self, situation: str, judgment_dimensions: List[str] = None) -> CausalInferenceResult:
        """
        因果推断主入口
        给定情境，输出因果假设和最佳解释
        """
        similar_events = find_similar_events(situation, max_results=5)
        hypotheses = self._generate_hypotheses(situation, similar_events)
        
        if self.adapter.is_configured() and hypotheses:
            hypotheses = self._llm_refine_hypotheses(situation, hypotheses)
        
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        reasoning_chain = self._build_reasoning_chain(hypotheses, similar_events)
        best = hypotheses[0] if hypotheses else None
        best_explanation = self._generate_best_explanation(best, situation)
        
        return CausalInferenceResult(
            situation=situation,
            hypotheses=hypotheses,
            best_explanation=best_explanation,
            reasoning_chain=reasoning_chain,
            confidence=hypotheses[0].confidence if hypotheses else 0.5,
            needs_more_data=len(similar_events) < 2
        )
    
    def _generate_hypotheses(self, situation: str, similar_events: List[dict]) -> List[CausalHypothesis]:
        """从历史事件生成因果假设"""
        hypotheses = []
        
        for event in similar_events:
            outcome = event.get("outcome")
            if not outcome:
                continue
            
            cause = event.get("task", "")[:100]
            effect = f"结果={outcome}"
            similarity = event.get("similarity", 0.7)
            
            hypotheses.append(CausalHypothesis(
                cause=cause,
                effect=effect,
                confidence=similarity * 0.8,
                evidence_for=[f"相似情境: {cause}", f"当时结果: {outcome}"],
                evidence_against=[],
                reasoning="基于相似历史事件的推断",
                source_events=[event.get("event_id")]
            ))
        
        return hypotheses
    
    def _llm_refine_hypotheses(self, situation: str, hypotheses: List[CausalHypothesis]) -> List[CausalHypothesis]:
        """用LLM精化因果假设"""
        prompt = f"""你是因果推理专家。分析当前情境的因果关系。

情境: {situation}

候选假设:
{json.dumps([{"cause": h.cause, "effect": h.effect, "conf": h.confidence} for h in hypotheses], ensure_ascii=False, indent=2)}

分析：哪些假设最可能成立？补充因果机制，指出反例。

输出JSON:
{{
    "refined_hypotheses": [
        {{
            "cause": "原因",
            "effect": "效果",
            "confidence": 0.0-1.0,
            "reasoning": "推理",
            "evidence_for": ["支持1"],
            "evidence_against": ["反例1"]
        }}
    ]
}}
"""
        
        try:
            response = self.adapter.complete(CompletionRequest(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.5,
            ))
            
            if response.success:
                import re
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    refined = data.get("refined_hypotheses", [])
                    return [
                        CausalHypothesis(
                            cause=h["cause"],
                            effect=h["effect"],
                            confidence=h.get("confidence", 0.5),
                            evidence_for=h.get("evidence_for", []),
                            evidence_against=h.get("evidence_against", []),
                            reasoning=h.get("reasoning", ""),
                            source_events=[]
                        )
                        for h in refined
                    ]
        except Exception:
            pass
        
        return hypotheses
    
    def _build_reasoning_chain(self, hypotheses: List[CausalHypothesis], similar_events: List[dict]) -> str:
        """构建推理链"""
        if not hypotheses:
            return "缺乏历史数据，无法建立因果推理链。"
        
        parts = ["因果推理链:"]
        for i, h in enumerate(hypotheses[:3]):
            parts.append(f"{i+1}. {h.cause} → {h.effect} (置信度: {h.confidence:.2f})")
        
        if similar_events:
            parts.append(f"\n基于 {len(similar_events)} 个相似事件")
        
        return "\n".join(parts)
    
    def _generate_best_explanation(self, hypothesis: CausalHypothesis, situation: str) -> str:
        """生成最佳解释"""
        if not hypothesis:
            return f"情境「{situation[:50]}」: 缺乏历史数据"
        
        explanation = f"为什么这个决策可能是对的：\n\n{hypothesis.cause}\n\n推理: {hypothesis.reasoning}\n置信度: {hypothesis.confidence:.0%}\n"
        
        if hypothesis.evidence_for:
            explanation += "\n支持证据:\n"
            for e in hypothesis.evidence_for[:3]:
                explanation += f"  • {e}\n"
        
        if hypothesis.evidence_against:
            explanation += "\n反例/风险:\n"
            for e in hypothesis.evidence_against[:3]:
                explanation += f"  ⚠ {e}\n"
        
        return explanation


def infer_causal_chain(situation: str, dimensions: List[str] = None) -> CausalInferenceResult:
    """快捷函数：因果推断"""
    engine = CausalInferenceEngine()
    return engine.infer(situation, dimensions)
