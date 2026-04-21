#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server.py — Juhuo MCP Server (FastMCP)

提供 4 个 MCP 工具：
- judgment_10d   — 十维判断
- judgment_verdict — 标记 verdict
- judgment_status — 系统状态
- benchmark_run   — GDPVal 测试

使用方式：
  # 直接运行（stdio 传输）
  python mcp_server.py

  # 或在 Claude Code / OpenClaw 中配置 MCP server
  {
    "mcpServers": {
      "juhuo": {
        "command": "python",
        "args": ["E:/juhuo/mcp_server.py"]
      }
    }
  }
"""
import sys
import os

# 确保从 juhuo 目录运行
_juhuo_dir = os.path.dirname(os.path.abspath(__file__))
if _juhuo_dir not in sys.path:
    sys.path.insert(0, _juhuo_dir)

print("[juhuo-mcp] Starting...", file=sys.stderr)
sys.stderr.flush()

try:
    from fastmcp import FastMCP
except ImportError:
    print("[juhuo-mcp] ERROR: fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

# ── 创建 FastMCP 服务器 ────────────────────────────────────────────────────────
mcp = FastMCP(
    "juhuo",
    instructions="Juhuo 十维判断系统。提供判断、反馈、状态查询、Benchmark 测试工具。",
)


# ── 工具 1: 十维判断 ──────────────────────────────────────────────────────────
@mcp.tool()
def judgment_10d(task: str, profile: str = None) -> dict:
    """
    对用户输入的决策困境进行十维判断分析。

    Args:
        task:    判断问题（如"要不要辞职创业？"）
        profile: 可选 Persona 名称

    Returns:
        verdict (str):       判断结论
        confidence (float):  置信度 0-1
        chain_id (str):     判断链 ID
        dimensions (dict):   各维度 {name: {score, reasoning}}
    """
    from subsystems.judgment.pipeline import check10d_full
    result = check10d_full(task)
    return {
        "verdict": result.get("verdict", ""),
        "confidence": round(result.get("confidence", 0), 3),
        "chain_id": result.get("chain_id", ""),
        "dimensions": {
            d.get("name", ""): {
                "score": round(d.get("score", 0), 3),
                "reasoning": d.get("reasoning", ""),
            }
            for d in result.get("dimensions", [])
        },
    }


# ── 工具 2: 标记判断结果 ──────────────────────────────────────────────────────
@mcp.tool()
def judgment_verdict(chain_id: str, correct: bool = None) -> dict:
    """
    标记某次判断的对错，让系统自我进化。

    Args:
        chain_id: 判断链 ID（来自 judgment_10d 的返回）
        correct:  True=正确，False=错误，None=删除记录

    Returns:
        {"status": "...", "chain_id": "...", "message": "..."}
    """
    from judgment.verdict_collector import (
        mark_verdict_correct,
        mark_verdict_wrong,
        remove_verdict,
    )

    if correct is None:
        remove_verdict(chain_id)
        return {"status": "removed", "chain_id": chain_id, "message": "已删除 verdict 记录"}

    if correct:
        mark_verdict_correct(chain_id)
        return {"status": "correct", "chain_id": chain_id, "message": "标记为正确，已进入进化反馈"}

    mark_verdict_wrong(chain_id)
    return {"status": "wrong", "chain_id": chain_id, "message": "标记为错误，已进入进化反馈"}


# ── 工具 3: 系统状态 ───────────────────────────────────────────────────────────
@mcp.tool()
def judgment_status() -> dict:
    """
    查看系统当前状态：维度信念 + verdict 统计。
    """
    from judgment.self_model.belief import get_belief_status
    from judgment.verdict_collector import get_verdict_stats

    beliefs = get_belief_status()
    verdicts = get_verdict_stats()

    return {
        "beliefs": beliefs,
        "verdicts": verdicts,
        "system": "juhuo v2.1",
    }


# ── 工具 4: GDPVal Benchmark ──────────────────────────────────────────────────
@mcp.tool()
def benchmark_run(cases: list = None) -> dict:
    """
    运行 GDPVal Benchmark 评估判断质量。

    Args:
        cases: 可选，要测试的案例 ID 列表（如 ["b001", "b002"]）
               None=运行全部 22 个案例

    Returns:
        accuracy, passed, failed, avg_confidence, gdval_grade
    """
    from subsystems.judgment.benchmark import Benchmark

    bench = Benchmark()
    if cases:
        report = bench.run_cases(cases)
    else:
        report = bench.run_all()

    return {
        "total_cases": report.total_cases,
        "passed": report.passed,
        "failed": report.failed,
        "accuracy": round(report.accuracy, 3),
        "avg_confidence": round(report.avg_confidence, 3),
        "gdval_grade": report.gdval_grade,
        "gdval_score": round(report.gdval_score, 1),
        "avg_time_ms": round(report.avg_time_ms, 0),
    }


# ── 启动 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # stdio 传输（MCP 标准，Claude Code/OpenClaw 均支持）
    mcp.run(transport="stdio")
