#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
protocol.py — Juhuo 判断协议

灵感来自Codex Rust的协议驱动设计

所有消息类型枚举:
- QUERY: 用户查询
- PRECHECK: 规则预检
- ANALYSIS: 维度分析
- VERDICT: 最终判决
- VERIFICATION: 验证
- EXECUTION: 执行
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


class JudgmentMessage(Enum):
    """判断消息类型枚举"""
    QUERY = "query"           # 用户查询
    PRECHECK = "precheck"     # 规则预检
    ANALYSIS = "analysis"     # 维度分析
    VERDICT = "verdict"       # 最终判决
    VERIFICATION = "verify"   # 验证
    EXECUTION = "execution"   # 执行
    COMPLETION = "completion" # 完成


class ExitCode(Enum):
    """执行退出码 - 灵感来自Codex"""
    SUCCESS = 0          # 可信，执行
    NEED_VERIFY = 1      # 需要验证
    REJECTED = 2         # 拒绝
    UNCERTAIN = 3        # 不确定
    TIMEOUT = 4          # 超时
    ERROR = 5            # 错误


class Decision(Enum):
    """判断决策枚举"""
    APPROVE = "approve"      # 批准
    REJECT = "reject"        # 拒绝
    UNCERTAIN = "uncertain"  # 不确定
    DEFER = "defer"          # 推迟


# ── 标准化消息 ─────────────────────────────────────────────────────
@dataclass
class JudgmentMessage:
    """标准化判断消息"""
    type: JudgmentMessage
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
    
    @staticmethod
    def from_dict(d: Dict) -> "JudgmentMessage":
        return JudgmentMessage(
            type=JudgmentMessage(d.get("type", "query")),
            session_id=d.get("session_id", ""),
            timestamp=d.get("timestamp", ""),
            payload=d.get("payload", {}),
        )


# ── ExitCode结果协议 ───────────────────────────────────────────────
@dataclass
class JudgmentResult:
    """
    标准化判断结果 - 灵感来自Codex ExecToolCallOutput
    
    exit_code:
    - 0 = SUCCESS (可信，执行)
    - 1 = NEED_VERIFY (需要验证)
    - 2 = REJECTED (拒绝)
    - 3 = UNCERTAIN (不确定)
    - 4 = TIMEOUT (超时)
    - 5 = ERROR (错误)
    """
    decision: Decision
    exit_code: ExitCode
    confidence: float                    # 0.0-1.0
    reasons: List[str] = field(default_factory=list)     # 支持理由
    warnings: List[str] = field(default_factory=list)   # 警告
    dimensions: Dict[str, float] = field(default_factory=dict)  # 各维度分数
    chain_id: str = ""
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "decision": self.decision.value,
            "exit_code": self.exit_code.value,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "dimensions": self.dimensions,
            "chain_id": self.chain_id,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }
    
    @staticmethod
    def from_dict(d: Dict) -> "JudgmentResult":
        return JudgmentResult(
            decision=Decision(d.get("decision", "uncertain")),
            exit_code=ExitCode(d.get("exit_code", 3)),
            confidence=d.get("confidence", 0.5),
            reasons=d.get("reasons", []),
            warnings=d.get("warnings", []),
            dimensions=d.get("dimensions", {}),
            chain_id=d.get("chain_id", ""),
            duration_ms=d.get("duration_ms", 0.0),
            timestamp=d.get("timestamp", ""),
        )
    
    def is_approved(self) -> bool:
        """是否可以执行"""
        return self.exit_code in [ExitCode.SUCCESS, ExitCode.NEED_VERIFY]
    
    def is_safe(self) -> bool:
        """是否安全"""
        return self.exit_code == ExitCode.SUCCESS and self.confidence >= 0.7
    
    def summary(self) -> str:
        """简短摘要"""
        return f"[{self.exit_code.name}] {self.decision.value} (置信度: {self.confidence:.0%})"


# ── 工厂函数 ────────────────────────────────────────────────────────
def make_result(
    decision: str,
    confidence: float,
    reasons: List[str] = None,
    warnings: List[str] = None,
    dimensions: Dict[str, float] = None,
    chain_id: str = "",
) -> JudgmentResult:
    """创建标准化判断结果"""
    # 根据confidence和warnings决定exit_code
    if warnings:
        exit_code = ExitCode.NEED_VERIFY
    elif confidence >= 0.7:
        exit_code = ExitCode.SUCCESS
    elif confidence >= 0.4:
        exit_code = ExitCode.UNCERTAIN
    else:
        exit_code = ExitCode.REJECTED
    
    # 根据decision决定
    if decision == "approve":
        d = Decision.APPROVE
    elif decision == "reject":
        d = Decision.REJECT
        exit_code = ExitCode.REJECTED
    else:
        d = Decision.UNCERTAIN
    
    return JudgmentResult(
        decision=d,
        exit_code=exit_code,
        confidence=confidence,
        reasons=reasons or [],
        warnings=warnings or [],
        dimensions=dimensions or {},
        chain_id=chain_id,
    )


# ── 协议验证 ───────────────────────────────────────────────────────
def validate_message(msg: Dict) -> bool:
    """验证消息格式"""
    required = ["type", "session_id", "payload"]
    return all(k in msg for k in required)


def validate_result(result: Dict) -> bool:
    """验证结果格式"""
    required = ["decision", "exit_code", "confidence"]
    return all(k in result for k in required)
