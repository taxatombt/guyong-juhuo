#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verifier.py — Juhuo 判断验证层

P1改进：加一层验证——judgment输出后，用不同角度反驳一次

参考 Claude Code 的 Verification Agent：在执行判断之前，
先问"这个判断有没有在合理化？"

核心思想：
- 判断 → 反驳 → 修订
- 如果反驳的置信度 > 0.7，说明原判断有漏洞，需要修订
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path

# LLM接入
from llm_adapter.minimax import get_adapter
from llm_adapter.base import CompletionRequest


class JudgmentVerifier:
    """判断验证器：自我反驳机制"""

    def __init__(self):
        self.adapter = get_adapter()
        self._rebuttal_prompt_template = self._build_rebuttal_prompt()

    def _build_rebuttal_prompt(self) -> str:
        return """你是批判性思维专家。给定一个判断，从反方角度找3个漏洞。

判断：{judgment_summary}

请分析：
1. 这个判断最可能的3个漏洞是什么？
2. 反方会怎么质疑这个判断？
3. 修正后的判断应该是什么？

输出格式（JSON）：
{{
    "rebuttals": ["漏洞1", "漏洞2", "漏洞3"],
    "confidence": 0.0-1.0,  // 反驳置信度，高=原判断有问题
    "revised_summary": "修正后的判断",
    "requires_revision": true/false
}}
"""

    def verify(self, judgment_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证判断结果
        
        Args:
            judgment_result: check10d的输出
            
        Returns:
            验证结果，包含反驳和是否需要修订
        """
        # 如果LLM未配置，返回空验证
        if not self.adapter.is_configured():
            return {
                "verified": False,
                "rebuttals": [],
                "confidence": 0.5,
                "revised_summary": None,
                "requires_revision": False,
                "reason": "LLM not configured"
            }

        # 提取判断摘要
        summary = self._extract_summary(judgment_result)
        
        prompt = self._rebuttal_prompt_template.format(judgment_summary=summary)
        
        try:
            response = self.adapter.complete(CompletionRequest(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.7,
            ))
            
            if not response.success:
                return {
                    "verified": False,
                    "rebuttals": [],
                    "confidence": 0.5,
                    "reason": f"LLM call failed: {response.error}"
                }
            
            # 解析JSON响应
            verification = self._parse_verification(response.content)
            
            return {
                "verified": True,
                "rebuttals": verification.get("rebuttals", []),
                "confidence": verification.get("confidence", 0.5),
                "revised_summary": verification.get("revised_summary"),
                "requires_revision": verification.get("requires_revision", False),
                "reason": "verified"
            }
            
        except Exception as e:
            return {
                "verified": False,
                "rebuttals": [],
                "confidence": 0.5,
                "reason": f"Exception: {e}"
            }

    def _extract_summary(self, result: Dict[str, Any]) -> str:
        """从判断结果中提取摘要"""
        task = result.get("task", "")
        dimensions = result.get("dimensions", [])
        answers = result.get("answers", {})
        weights = result.get("weights", {})
        
        summary_parts = [f"问题：{task}", ""]
        summary_parts.append("各维度分析：")
        
        for dim in dimensions[:5]:  # 只取前5个最重要维度
            answer = answers.get(dim, "未分析")
            weight = weights.get(dim, 0)
            summary_parts.append(f"- {dim}(权重{weight:.2f}): {answer[:100]}")
        
        return "\n".join(summary_parts)

    def _parse_verification(self, content: str) -> Dict[str, Any]:
        """解析验证结果"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # 降级：简单解析
        return {
            "rebuttals": [],
            "confidence": 0.5,
            "requires_revision": False
        }


def verify_judgment(judgment_result: Dict[str, Any]) -> Dict[str, Any]:
    """快捷函数：验证判断"""
    verifier = JudgmentVerifier()
    return verifier.verify(judgment_result)
