#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verification_agent.py — Juhuo 独立验证 Agent

借鉴 Claude Code Verification Agent：最严格的验证

功能：
- 验证判断结果的正确性
- 挑毛病，不留情面
- 只有通过了才放行
"""

from __future__ import annotations
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from judgment.logging_config import get_logger
log = get_logger("juhuo.verification_agent")


# 验证级别
class VerifyLevel:
    NORMAL = "normal"      # 普通验证
    STRICT = "strict"      # 严格验证
    PARANOID = "paranoid"  # 偏执验证


@dataclass
class VerifyResult:
    """验证结果"""
    passed: bool
    issues: List[str]      # 发现的问题
    suggestions: List[str] # 改进建议
    confidence: float      # 验证置信度 0-1
    timestamp: str


@dataclass
class DimensionVerify:
    """单维度验证"""
    dimension: str
    score: float
    issue: str = ""        # 问题描述
    passed: bool = True


class VerificationAgent:
    """
    验证 Agent
    
    不信任判断结果，必须逐条验证。
    """
    
    def __init__(self, level: str = VerifyLevel.NORMAL):
        self.level = level
        self.history: List[VerifyResult] = []
    
    def verify_judgment(self, judgment_result: Dict) -> VerifyResult:
        """
        验证判断结果
        
        Args:
            judgment_result: check10d() 返回的结果
            
        Returns:
            VerifyResult
        """
        log.info(f"Verifying judgment: level={self.level}")
        issues = []
        suggestions = []
        
        # 1. 检查必要维度是否被跳过
        skipped = judgment_result.get("skipped", [])
        if skipped:
            issues.append(f"⚠️ 以下维度被跳过: {', '.join(skipped)}")
            suggestions.append("考虑是否真的可以跳过这些维度")
        
        # 2. 检查复杂度与维度选择是否匹配
        complexity = judgment_result.get("complexity", "normal")
        must_check = judgment_result.get("must_check", [])
        
        if complexity == "critical" and len(must_check) < 5:
            issues.append(f"🔴 复杂度为 critical，但只检视了 {len(must_check)} 个维度")
            suggestions.append("critical 问题至少检视 5+ 维度")
        
        # 3. 检查各维度分析质量
        if "answers" in judgment_result:
            for dim, answer in judgment_result["answers"].items():
                dim_result = self._verify_dimension(dim, answer)
                if not dim_result.passed:
                    issues.append(f"  {dim}: {dim_result.issue}")
                    suggestions.append(f"  {dim}: 补充 {answer[:30]}...")
        
        # 4. 检查推荐结果
        recommendation = judgment_result.get("recommendation", "")
        if not recommendation:
            issues.append("⚠️ 没有给出推荐结论")
            suggestions.append("给出明确的推荐方向")
        
        # 5. 置信度检查
        confidence = judgment_result.get("confidence", 0)
        if confidence < 0.5 and len(issues) < 2:
            issues.append(f"⚠️ 置信度 {confidence:.0%} 较低")
            suggestions.append("收集更多信息再下结论")
        
        # 6. 偏执模式额外检查
        if self.level == VerifyLevel.PARANOID:
            paranoid_issues = self._paranoid_check(judgment_result)
            issues.extend(paranoid_issues)
        
        # 决策
        passed = len(issues) == 0 or all("⚠️" in i for i in issues)
        
        result = VerifyResult(
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            confidence=1.0 - (len(issues) * 0.1),
            timestamp=datetime.now().isoformat()
        )
        
        self.history.append(result)
        log.info(f"Verification result: passed={passed}, issues={len(issues)}")
        
        return result
    
    def _verify_dimension(self, dimension: str, answer: str) -> DimensionVerify:
        """验证单个维度"""
        result = DimensionVerify(dimension=dimension, score=1.0)
        
        # 太短
        if len(answer) < 20:
            result.issue = "回答太短，需要更详细"
            result.score = 0.5
            result.passed = False
        
        # 太泛
        generic_patterns = ["可以考虑", "需要综合考虑", "视情况而定"]
        if any(p in answer for p in generic_patterns):
            result.issue = "回答太泛泛，没有具体分析"
            result.score = 0.6
            result.passed = False
        
        return result
    
    def _paranoid_check(self, judgment_result: Dict) -> List[str]:
        """偏执模式额外检查"""
        issues = []
        
        # 检查是否有遗漏的关键信息
        task = judgment_result.get("task", "")
        if "利弊" in task or "优缺点" in task:
            if "pros" not in judgment_result and "cons" not in judgment_result:
                issues.append("🔴 没有区分利弊")
        
        # 检查是否有情绪影响
        if judgment_result.get("emotional_impact"):
            issues.append("⚠️ 存在情绪影响，需要理性核对")
        
        return issues
    
    def verify_chain(self, chain_id: str) -> VerifyResult:
        """验证历史判断链"""
        # 从数据库加载
        from judgment.judgment_db import get_conn
        
        with get_conn() as c:
            row = c.execute(
                "SELECT * FROM judgments WHERE chain_id = ?", (chain_id,)
            ).fetchone()
            
            if not row:
                return VerifyResult(
                    passed=False,
                    issues=["Chain not found"],
                    suggestions=[],
                    confidence=0,
                    timestamp=datetime.now().isoformat()
                )
            
            # 重建判断结果
            result = {
                "task": row["task_text"],
                "dimensions": json.loads(row["dimensions"]) if row["dimensions"] else [],
                "answers": json.loads(row["answers"]) if row["answers"] else {},
                "complexity": row.get("complexity", "normal")
            }
            
            return self.verify_judgment(result)
    
    def get_history(self, limit: int = 10) -> List[VerifyResult]:
        """获取验证历史"""
        return self.history[-limit:]
    
    def get_pass_rate(self) -> float:
        """获取通过率"""
        if not self.history:
            return 1.0
        return sum(1 for r in self.history if r.passed) / len(self.history)


# 全局验证 Agent
_verification_agent: Optional[VerificationAgent] = None


def get_verifier(level: str = VerifyLevel.NORMAL) -> VerificationAgent:
    """获取验证 Agent"""
    global _verification_agent
    if _verification_agent is None:
        _verification_agent = VerificationAgent(level)
    return _verification_agent


def verify_and_correct(judgment_result: Dict) -> Dict:
    """
    验证并修正判断结果
    
    Returns:
        (verified_result, corrections_applied)
    """
    verifier = get_verifier(VerifyLevel.STRICT)
    verify_result = verifier.verify_judgment(judgment_result)
    
    corrections = []
    if not verify_result.passed:
        # 根据验证结果补充信息
        for suggestion in verify_result.suggestions:
            if "补充" in suggestion:
                dim = suggestion.split(":")[0].strip()
                corrections.append(f"建议补充 {dim} 维度的分析")
    
    return {
        "original": judgment_result,
        "verification": asdict(verify_result),
        "corrections": corrections
    }


if __name__ == "__main__":
    # 测试
    agent = VerificationAgent(VerifyLevel.STRICT)
    
    test_result = {
        "task": "要不要创业",
        "complexity": "complex",
        "must_check": ["cognitive", "economic"],
        "skipped": ["moral", "social"],
        "answers": {
            "cognitive": "需要考虑市场",
        },
        "recommendation": "继续观望",
        "confidence": 0.6
    }
    
    result = agent.verify_judgment(test_result)
    print(f"\n验证结果: {'通过' if result.passed else '未通过'}")
    print(f"问题数: {len(result.issues)}")
    for issue in result.issues:
        print(f"  - {issue}")
