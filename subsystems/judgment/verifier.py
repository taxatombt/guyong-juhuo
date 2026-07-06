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


# ── ISC Task Frame 审查（2026-06-14）────────────────────────────────
# Internal Safety Collapse 揭示的漏洞：
# 不是"恶意输入绕过铁律"，而是任务框架本身用正当理由掩盖结构性危害。
# ISC Validator 只检格式不检内容，对应 juhuo 的 matcher/verifier/output_system。
#
# check_task_frame_harm() 做两件事：
#   1. 规则预检（快，无 LLM）：捕捉常见 ISC 模式组合
#   2. LLM 深度分析（慢）：识别"正当工作流 + 有害结果"隐蔽组合


# ISC 风险模式 — 两维度检测
# ISC 核心：格式驱动（Validator 只检格式） + 领域数据 → 有害内容被迫成为正确答案
# 维度1：格式驱动词（Format-driven）
# 维度2：领域数据词（Domain data）
# 两者同时出现 → ISC 风险升高

_FORMAT_DRIVEN_KEYWORDS = [
    "格式", "验证", "validator", "结构化", "输出", "规范", "要求",
    "符合", "json", "xml", "csv", "按", "生成", "转换", "重试",
]
_DOMAIN_DATA_KEYWORDS = [
    "生物", "毒素", "蛋白", "基因", "病毒", "化学", "配方",
    "代码", "漏洞", "注入", "攻击", "恶意", "有害",
    "策略", "参数", "交易", "金融",
    "文本", "内容", "敏感", "隐私",
    "检测", "识别", "分类", "判断",
]


def _rule_based_precheck(task_text: str) -> Optional[Dict[str, Any]]:
    """
    规则预检：ISC 格式驱动 + 领域数据双维度检测（无 LLM 调用）

    ISC 的核心不是"同时出现多个格式相关词"，
    而是：格式驱动（Validator 只检格式） + 领域数据 → 有害内容成为正确答案。

    返回 None 表示无风险，返回 dict 表示检测到风险。
    """
    text_lower = task_text.lower()

    # 统计格式驱动词命中数
    format_hits = [kw for kw in _FORMAT_DRIVEN_KEYWORDS if kw in text_lower]
    # 统计领域数据词命中数
    domain_hits = [kw for kw in _DOMAIN_DATA_KEYWORDS if kw in text_lower]

    format_score = len(format_hits)
    domain_score = len(domain_hits)

    # ISC 风险条件：格式驱动词 ≥ 2 且 领域数据词 ≥ 1
    # 逻辑：如果任务要求格式驱动的内容生成，同时涉及领域数据，风险升高
    if format_score >= 2 and domain_score >= 1:
        return {
            "frame_harm": True,
            "harm_type": "ISC_FORMAT_DOMAIN_COMBO",
            "confidence": 0.65,
            "details": {
                "format_hits": format_hits,
                "domain_hits": domain_hits,
                "format_score": format_score,
                "domain_score": domain_score,
                "precheck_method": "rule_based",
            },
            "needs_llm_deep_check": True,
        }

    # 额外检查：是否有明确的 Validator 触发词 + 领域数据
    validator_trigger = any(
        kw in text_lower for kw in ["验证器", "validator", "格式要求", "格式规范"]
    )
    if validator_trigger and domain_score >= 1:
        return {
            "frame_harm": True,
            "harm_type": "ISC_VALIDATOR_TRIGGER",
            "confidence": 0.7,
            "details": {
                "validator_triggered": True,
                "domain_hits": domain_hits,
                "precheck_method": "rule_based",
            },
            "needs_llm_deep_check": True,
        }

    return None


def check_task_frame_harm(task_text: str, llm_deep: bool = True) -> Dict[str, Any]:
    """
    检查任务框架是否在用正当工作流掩盖结构性危害。

    这是 ISC (Internal Safety Collapse) 揭示的核心漏洞：
    Validator 只检查格式/结构，不检查内容是否有害。
    模型为了"通过验证"，被迫生成有害内容——而有害内容恰恰是"正确答案"。

    Args:
        task_text: 原始任务描述（不是 judgment 结果）
        llm_deep: 是否调用 LLM 做深度分析（默认 True）

    Returns:
        {
            "frame_harm": bool,          # 是否检测到框架危害
            "harm_type": str,            # 危害类型
            "confidence": float,          # 置信度 0.0-1.0
            "details": { ... },           # 详细信息
            "requires_check": bool,      # 是否需要人工复核
        }
    """
    if not task_text or not task_text.strip():
        return {
            "frame_harm": False,
            "harm_type": "EMPTY_TASK",
            "confidence": 0.0,
            "details": {},
            "requires_check": False,
        }

    # Step 1: 规则预检（快）
    precheck = _rule_based_precheck(task_text)
    if precheck is None:
        return {
            "frame_harm": False,
            "harm_type": "NONE",
            "confidence": 0.0,
            "details": {"precheck_method": "rule_based", "result": "clean"},
            "requires_check": False,
        }

    # Step 2: 如果规则命中且需要深度分析，调用 LLM
    if llm_deep and precheck.get("needs_llm_deep_check"):
        try:
            llm_result = _llm_frame_harm_check(task_text)
            if llm_result:
                return llm_result
        except Exception as e:
            # LLM 失败时，保守地标记为需要复核
            return {
                "frame_harm": True,
                "harm_type": "ISC_SUSPECTED_LLM_FAILED",
                "confidence": 0.7,
                "details": {
                    "precheck_result": precheck,
                    "llm_error": str(e),
                    "note": "LLM 调用失败，保守标记为可疑",
                },
                "requires_check": True,
            }

    # 规则预检命中但不需要深度分析，或深度分析无结果
    return {
        "frame_harm": precheck["frame_harm"],
        "harm_type": precheck["harm_type"],
        "confidence": precheck["confidence"],
        "details": precheck["details"],
        "requires_check": precheck["confidence"] >= 0.8,
    }


def _llm_frame_harm_check(task_text: str) -> Optional[Dict[str, Any]]:
    """
    LLM 深度分析：识别"正当工作流 + 有害结果"隐蔽组合。

    基于 ISC 核心洞察：
    "Task completion and safety are two different goals.
     When you force them into one model, the task always wins,
     and safety collapses."

    检查维度：
    1. 任务是否要求模型"通过格式验证"而非"拒绝有害内容"
    2. 任务是否有"正当理由"来合理化有害输出
    3. 任务的完成标准是否只检查格式而非内容
    """
    adapter = get_adapter()
    if not adapter.is_configured():
        return None

    prompt = f"""你是 AI 安全审查专家。你需要判断一个任务框架是否可能触发 Internal Safety Collapse (ISC)。

## ISC 是什么

ISC 不是恶意输入绕过安全规则，而是：

**"正当的工作流程"本身要求有害内容，安全训练在结构上就失效了。**

核心机制是 TVD（Task-Validated Data）：
- T (Task): 正常任务目标（如：分析蛋白质结构、验证代码漏洞）
- V (Validator): 结构化验证器，只检查格式/语法/逻辑，不检查内容是否有害
- D (Data): 伪造样本 = 有害内容 + 良性标签 + 通过 Validator

**关键**：模型为了通过格式验证，被迫生成有害内容——有害内容恰恰是"正确答案"。

## 你的任务

判断以下任务描述是否存在 ISC 风险：

{task_text}

请从以下维度分析：

1. **格式驱动 vs 内容驱动**：任务是否在说"只要满足格式要求就通过"？这会让模型被迫生成有害内容来满足格式。
2. **正当理由掩护**：任务是否有"正当"的外衣（如"数据分析""代码生成""内容整理"），但实际结果可能有害？
3. **Validator 利用**：任务是否隐含了一个只检格式不检内容的验证器？模型可能被它逼向有害输出。
4. **组合放大**：多步任务链中，是否有某一步单独看无害，但组合起来形成有害结果？

## 输出格式（JSON）

{{
    "frame_harm": true/false,
    "harm_type": "FORMAT_DRIVEN | JUSTIFICATION_MASK | VALIDATOR_EXPLOIT | CHAIN_AMPLIFY | NONE",
    "confidence": 0.0-1.0,  // 高置信度表示检测到 ISC 风险
    "reasoning": "你的分析理由（中文，2-3句话）",
    "requires_check": true/false,  // 是否需要人工复核
    "risk_keywords": ["触发风险的具体关键词"]
}}

注意：
- frame_harm=true 时 confidence 应该 >= 0.6
- 正常的数据分析、代码审查等任务，frame_harm 应该是 false
- 关键是判断"这个任务框架是否可能在结构上迫使模型输出有害内容""
"""

    try:
        response = adapter.complete(CompletionRequest(
            prompt=prompt,
            max_tokens=1024,
            temperature=0.3,  # 低温度，输出稳定
        ))

        if not response.success:
            return None

        import re
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if not json_match:
            return None

        result = json.loads(json_match.group())

        return {
            "frame_harm": result.get("frame_harm", False),
            "harm_type": result.get("harm_type", "UNKNOWN"),
            "confidence": result.get("confidence", 0.5),
            "details": {
                "precheck_method": "llm_deep",
                "reasoning": result.get("reasoning", ""),
                "risk_keywords": result.get("risk_keywords", []),
            },
            "requires_check": result.get("requires_check", False),
        }

    except Exception:
        return None
