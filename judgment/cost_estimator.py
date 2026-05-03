#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cost_estimator.py — Juhuo 行动成本估算器

来源：huggingface/ml-intern cost_estimation.py 启发

为每次判断后的行动预估执行成本：
- 金钱成本（外部 API 调用费用）
- 时间成本（执行耗时预估）
- 风险成本（敏感操作、数据变更）

三类审批触发：
1. 高金钱成本（>$10）→ 需确认
2. 不可逆操作（删除、覆盖）→ 需确认
3. 外部网络调用（>1次）→ 需确认

来源：ml-intern 的 ApprovalPolicy（HF jobs 预算守卫）
"""

import re
import time
from dataclasses import dataclass
from typing import Optional

# ── 成本表（ml-intern 风格，按实际服务商定价） ─────────────────────────

# 外部 API 费用（$/次），基于实际定价
API_COST_PER_CALL = {
    "openai": 0.01,      # GPT-4o mini 约 $0.01/1M input
    "anthropic": 0.015,   # Claude 3.5 Sonnet 约 $0.015/1M input
    "minimax": 0.005,    # MiniMax M2.7 约 $0.005/1M input
    "deepseek": 0.001,    # DeepSeek V3 约 $0.001/1M input
    "github_api": 0.01,    # GitHub API 免费额度后 $0.01/次
    "hf_api": 0.0,        # HF API 免费
    "web_search": 0.005,  # 搜索 API 约 $0.005/次
}

# 执行时间预估（秒）
EXEC_TIME_ESTIMATE = {
    "llm_call": 3,        # LLM API 调用
    "file_write": 0.5,    # 文件写入
    "file_read": 0.2,     # 文件读取
    "web_request": 2,     # 网络请求
    "git_clone": 30,      # git clone 大仓库
    "git_push": 5,        # git push
    "database_write": 1,  # 数据库写入
    "api_call": 2,        # 通用 API 调用
}

# 高风险操作关键词（不可逆）
HIGH_RISK_PATTERNS = [
    (r"rm\s+-rf", "递归强制删除", 10.0),
    (r"rm\s+-\w*r", "强制删除文件", 5.0),
    (r"drop\s+table", "删除数据库表", 10.0),
    (r"delete\s+from", "删除数据库记录", 5.0),
    (r"truncate", "清空表", 10.0),
    (r"overwrite", "覆写文件", 3.0),
    (r"force push", "强制推送git", 5.0),
    (r"--force\b", "强制覆盖", 3.0),
    (r"shutdown", "关闭服务", 10.0),
    (r"kill\s+-9", "强制终止进程", 5.0),
    (r"eval\s*\(", "执行动态代码", 10.0),
]

# 外部网络调用关键词
EXTERNAL_API_PATTERNS = [
    (r"https?://", "外部网络请求"),
    (r"curl\s+", "curl 网络请求"),
    (r"wget\s+", "wget 下载"),
    (r"requests\.(get|post)", "Python requests"),
    (r"httpx\.(get|post)", "httpx 请求"),
    (r"Invoke-WebRequest", "PowerShell 网络请求"),
]


@dataclass
class CostEstimate:
    """行动成本估算结果"""
    money_cost_usd: float      # 金钱成本（美元）
    time_cost_sec: float       # 时间成本（秒）
    risk_score: float          # 风险评分（0-10）
    risk_reasons: list[str]    # 风险原因
    requires_approval: bool    # 是否需要审批
    approval_reason: str | None  # 审批原因
    label: str | None          # 简短描述


def estimate_action_cost(action_text: str) -> CostEstimate:
    """
    估算单个行动的成本。

    Args:
        action_text: 行动描述文本（bash命令、API调用等）

    Returns:
        CostEstimate
    """
    action_lower = action_text.lower()

    # ── 金钱成本 ──
    money = 0.0

    # LLM API 调用
    if "llm" in action_lower or "chat" in action_lower or "completion" in action_lower:
        for provider, cost in API_COST_PER_CALL.items():
            if provider in action_lower:
                money += cost
                break
        else:
            money += API_COST_PER_CALL.get("minimax", 0.01)

    # 外部 API 调用
    for provider, cost in API_COST_PER_CALL.items():
        if provider in action_lower and "api" in action_lower:
            money += cost

    # GitHub API
    if "github" in action_lower and any(k in action_lower for k in ["api", "gh ", "pull", "pr "]):
        money += API_COST_PER_CALL["github_api"]

    # Web search
    if "search" in action_lower or "google" in action_lower or "bing" in action_lower:
        money += API_COST_PER_CALL["web_search"]

    # ── 时间成本 ──
    time_cost = 0.5  # 默认基准时间

    for op, sec in EXEC_TIME_ESTIMATE.items():
        if op.replace("_", "-") in action_lower or op in action_lower:
            time_cost = max(time_cost, sec)
            break

    # 检测大仓库 clone
    if re.search(r"git\s+clone|git\s+pull", action_text):
        # 检查是否包含大仓库关键词
        if any(k in action_lower for k in ["pytorch", "tensorflow", "huggingface", "transformers"]):
            time_cost = 120  # 大模型仓库 clone 需要 2 分钟
        elif "git clone" in action_lower:
            time_cost = 30
        elif "git push" in action_lower:
            time_cost = 5
        elif "git pull" in action_lower:
            time_cost = 15

    # ── 风险评分 ──
    risk_score = 0.0
    risk_reasons: list[str] = []

    for pattern, reason, score in HIGH_RISK_PATTERNS:
        if re.search(pattern, action_text, re.IGNORECASE):
            risk_score += score
            risk_reasons.append(reason)

    # 外部网络调用计数
    external_calls = 0
    for pattern, reason in EXTERNAL_API_PATTERNS:
        matches = re.findall(pattern, action_text, re.IGNORECASE)
        external_calls += len(matches)

    if external_calls >= 3:
        risk_score += 2.0
        risk_reasons.append(f"多次外部调用({external_calls}次)")
    elif external_calls >= 1:
        risk_score += 0.5

    # ── 审批判断 ──
    requires_approval = False
    approval_reason: str | None = None

    if money > 10.0:
        requires_approval = True
        approval_reason = f"高金钱成本 ${money:.2f}"
    elif risk_score >= 10.0:
        requires_approval = True
        approval_reason = f"高风险操作 (评分={risk_score:.1f})：{' '.join(risk_reasons[:2])}"
    elif risk_score >= 5.0 and external_calls >= 1:
        requires_approval = True
        approval_reason = f"中等风险 + 外部调用：{' '.join(risk_reasons[:2])}"
    elif time_cost > 120:
        requires_approval = True
        approval_reason = f"长时间操作（预估{time_cost:.0f}秒）"

    # 风险评分上限
    risk_score = min(risk_score, 10.0)

    return CostEstimate(
        money_cost_usd=money,
        time_cost_sec=time_cost,
        risk_score=risk_score,
        risk_reasons=risk_reasons,
        requires_approval=requires_approval,
        approval_reason=approval_reason,
        label=_make_label(money, time_cost, risk_score),
    )


def _make_label(money: float, time_cost: float, risk: float) -> str:
    """生成简短标签"""
    parts = []
    if money > 0.01:
        parts.append(f"${money:.3f}")
    if time_cost > 60:
        parts.append(f"{time_cost/60:.0f}min")
    elif time_cost > 5:
        parts.append(f"{time_cost:.0f}s")
    if risk >= 5:
        parts.append(f"⚠{risk:.0f}")
    return " ".join(parts) if parts else "free"


def estimate_batch_cost(actions: list[str]) -> list[CostEstimate]:
    """批量估算多个行动的成本。"""
    return [estimate_action_cost(a) for a in actions]


# ── 单元测试 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test 1: 普通文件写入 → 不需要审批
    cost1 = estimate_action_cost("write_file(path='test.py', content='# hello')")
    assert not cost1.requires_approval, f"普通写入被错误标记为需要审批：{cost1.approval_reason}"
    assert cost1.risk_score < 5, f"普通写入风险评分过高：{cost1.risk_score}"
    print(f"✅ Test 1: 普通写入 OK ({cost1.label})")

    # Test 2: rm -rf → 高风险，需要审批
    cost2 = estimate_action_cost("rm -rf /tmp/test_dir")
    assert cost2.requires_approval, "rm -rf 未标记为需要审批"
    assert cost2.risk_score >= 5, f"rm -rf 风险评分过低：{cost2.risk_score}"
    assert "递归强制删除" in cost2.risk_reasons
    print(f"✅ Test 2: rm -rf OK ({cost2.label}, risk={cost2.risk_score})")

    # Test 3: git clone 大仓库 → 长时间，需要审批
    cost3 = estimate_action_cost("git clone https://github.com/pytorch/pytorch.git")
    assert cost3.time_cost_sec >= 60, f"大仓库 clone 时间预估过低：{cost3.time_cost_sec}s"
    print(f"✅ Test 3: git clone 大仓库 OK ({cost3.label}, {cost3.time_cost_sec}s)")

    # Test 4: LLM 调用 → 有金钱成本
    cost4 = estimate_action_cost("llm_call(provider='minimax', prompt='hello')")
    assert cost4.money_cost_usd > 0, f"LLM 调用金钱成本为 0：{cost4.money_cost_usd}"
    assert not cost4.requires_approval, f"LLM 调用被错误标记为需要审批：{cost4.approval_reason}"
    print(f"✅ Test 4: LLM 调用 OK ({cost4.label})")

    # Test 5: 批量估算
    costs = estimate_batch_cost([
        "write_file(path='a.txt', content='hi')",
        "rm -rf /tmp/test",
        "git clone https://github.com/transformers/transformers.git",
    ])
    assert len(costs) == 3
    assert costs[0].requires_approval == False
    assert costs[1].requires_approval == True
    print(f"✅ Test 5: 批量估算 OK")

    print("\n所有测试通过 ✅")

