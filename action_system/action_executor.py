#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-8: action_executor 结果写入 experiences 表（behavior 数据流闭环）

问题：action_executor.execute() 调 _log_execution()（写 JSONL）+ _verify_and_feedback()（写 evolver），
     但 experiences 表缺少工具调用上下文（action_channel / execution_result）

修复：在 _verify_and_feedback() 里加 log_agent_behavior() 调用，
     把行为结果（channel / execution_result / outcome_score）写入 experiences 表

行为闭环流程：
  router.check10d_and_execute()
    → action_executor.execute(channel=xxx)
      → _log_execution()          # 写 JSONL
      → _verify_and_feedback()    # 写 evolver + experiences
        → verify_outcome(chain_id, ...)  # evolver 更新权重
        → log_agent_behavior(...)       # experiences 表记录行为
"""
import json
import time
import subprocess
import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# ── 路径配置 ──────────────────────────────────────────────────────────────
_SELF_DIR = Path(__file__).parent
_ACTION_LOG = _SELF_DIR.parent / "data" / "actions" / "execution_log.jsonl"
_EVOLUTIONS_DIR = _SELF_DIR.parent / "data" / "evolutions"
os.makedirs(os.path.dirname(_ACTION_LOG), exist_ok=True)

# ── Dataclass ────────────────────────────────────────────────────────────────
@dataclass
class ExecutionResult:
    """单次执行的结果"""
    execution_id: str
    chain_id: str
    channel: str
    verdict: str
    action_description: str
    actual_result: str
    outcome_score: float
    score: float  # alias for outcome_score (compatibility)
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActionRolloutEngine:
    def __init__(self, num_rollouts: int = 3): self.num_rollouts = num_rollouts

    def rollout(self, task: str, verdict: str = '', user_context: dict = None) -> list:
        candidates = []
        for i in range(self.num_rollouts):
            plan = self._generate_plan(task, verdict, "auto", "balanced", user_context or {})
            candidates.append(plan)
        return candidates

    def select_best(self, candidates: list, safe_mode: bool = True) -> dict:
        if not candidates: return {}
        scored = [(c, self.compute_reward(c, "", "", {})) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if safe_mode else scored[abs(_rand()) % len(scored)][0]

    def compute_reward(self, candidate: dict, task: str, verdict: str, ctx: dict) -> tuple:
        feasibility = self._feasibility_score(candidate, task, ctx)
        risk = candidate.get("risk", "medium")
        risk_score = {"low": 1.0, "medium": 0.7, "high": 0.3}.get(risk, 0.5)
        return (feasibility * 0.4 + risk_score * 0.6,)

    def _generate_plan(self, task: str, verdict: str, channel: str, strategy: str, ctx: dict) -> tuple:
        action = f"[{channel.upper()}] {verdict[:40]}"
        return {"plan": action, "strategy": strategy, "risk": "medium", "channel": channel}

    def _feasibility_score(self, candidate: dict, task: str, ctx: dict) -> float:
        return 0.6 + (_rand() % 40) / 100


def _rand() -> int:
    try:
        import random
        return random.randint(0, 99)
    except:
        return 50


# ── ActionExecutor ──────────────────────────────────────────────────────────
class ActionExecutor:
    def __init__(self): self._engine = ActionRolloutEngine()

    def _execute(self, task: str, verdict: str, channel: str) -> dict:
        """执行入口（已存在，内容不变）"""
        # 占位，实际实现在下面各个 execute_via_xxx
        return {}

    # 通道1: Benchmark 验证 ─────────────────────────────────────────────────
    def execute_via_benchmark(self, task: str, expected_verdict: str = "") -> Dict[str, Any]:
        from subsystems.judgment.benchmark import run_benchmark
        exec_id = f"bench_{int(time.time()*1000)}"
        chain_id = f"bench_chain_{int(time.time()*1000)}"
        action_desc = f"Benchmark验证: {task[:60]}"
        score = 0.0
        try:
            result = run_benchmark(task, expected_verdict=expected_verdict)
            actual_result = json.dumps(result, ensure_ascii=False)[:1000]
            score = result.get("score", 0.0)
        except Exception as e:
            actual_result = f"Benchmark error: {e}"
            score = 0.0
        return {
            "execution_id": exec_id, "chain_id": chain_id,
            "channel": "benchmark", "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": score, "score": score,
            "timestamp": datetime.now().isoformat(),
        }

    # 通道2: Hermes ────────────────────────────────────────────────────────
    def execute_via_hermes(self, task: str, verdict: str = "") -> Dict[str, Any]:
        exec_id = f"hermes_{int(time.time()*1000)}"
        chain_id = f"hermes_chain_{int(time.time()*1000)}"
        try:
            from judgment.closed_loop import snapshot_judgment
            _dims = ["cognitive", "economic", "temporal"]
            snapshot_judgment(
                chain_id=chain_id, task_text=task, dimensions=_dims,
                weights={d: 1.0 for d in _dims},
                result={"verdict": verdict, "answers": {}, "confidence": 0.5,
                        "dim_confidence": {}, "emotion": {}, "curiosity": {}},
                complexity="complex",
            )
        except Exception: pass

        action_desc = f"Hermes执行: {task[:60]}"
        try:
            result = subprocess.run(
                ["copaw", "agents", "chat", "--to", "hermes", "--message", task],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            actual_result = result.stdout[:2000] if result.stdout else ""
            if not actual_result: actual_result = result.stderr[:500] if result.stderr else "(no output)"
            outcome_score = 1.0 if result.returncode == 0 else 0.3
        except FileNotFoundError:
            actual_result = "copaw not found in PATH, Hermes not available"
            outcome_score = 0.0
        except subprocess.TimeoutExpired:
            actual_result = "Hermes execution timed out (120s)"
            outcome_score = 0.5
        except Exception as e:
            actual_result = f"Hermes error: {e}"
            outcome_score = 0.0

        return {
            "execution_id": exec_id, "chain_id": chain_id,
            "channel": "hermes", "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": outcome_score, "score": outcome_score,
            "timestamp": datetime.now().isoformat(),
        }

    # 通道3: Claude Code ────────────────────────────────────────────────────
    def execute_via_claude_code(self, task: str, verdict: str = "") -> Dict[str, Any]:
        exec_id = f"cc_{int(time.time()*1000)}"
        chain_id = f"cc_chain_{int(time.time()*1000)}"
        action_desc = f"Claude Code执行: {task[:60]}"
        try:
            from judgment.closed_loop import snapshot_judgment
            _dims = ["cognitive", "economic", "temporal"]
            snapshot_judgment(
                chain_id=chain_id, task_text=task, dimensions=_dims,
                weights={d: 1.0 for d in _dims},
                result={"verdict": verdict, "answers": {}, "confidence": 0.5,
                        "dim_confidence": {}, "emotion": {}, "curiosity": {}},
                complexity="complex",
            )
        except Exception: pass

        try:
            result = subprocess.run(
                ["claude", "--print", "--no-input", task],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            actual_result = result.stdout[:2000] if result.stdout else ""
            if not actual_result: actual_result = result.stderr[:500] if result.stderr else "(no output)"
            outcome_score = 1.0 if result.returncode == 0 else 0.3
        except FileNotFoundError:
            actual_result = "claude not found in PATH"
            outcome_score = 0.0
        except subprocess.TimeoutExpired:
            actual_result = "Claude Code timed out (120s)"
            outcome_score = 0.5
        except Exception as e:
            actual_result = f"Claude Code error: {e}"
            outcome_score = 0.0

        return {
            "execution_id": exec_id, "chain_id": chain_id,
            "channel": "claude_code", "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": outcome_score, "score": outcome_score,
            "timestamp": datetime.now().isoformat(),
        }

    # 通道4: Codex CLI（everything-copilot-cli 多AI编排模式）
    # 来源: drvoss/everything-copilot-cli - 11个编排模式之一
    def execute_via_codex(self, task: str, verdict: str = "") -> Dict[str, Any]:
        """
        通过 OpenAI Codex CLI 执行代码任务。
        everything-copilot-cli "Shell Invocation" 模式：copilot --via codex
        
        Codex CLI 优势:
        - 快速代码补全/生成
        - 适合 snippet/模板/小函数
        - 比 Claude Code 更轻量
        """
        exec_id = f"codex_{int(time.time()*1000)}"
        chain_id = f"codex_chain_{int(time.time()*1000)}"
        action_desc = f"Codex执行: {task[:60]}"
        try:
            from judgment.closed_loop import snapshot_judgment
            _dims = ["cognitive", "economic"]
            snapshot_judgment(
                chain_id=chain_id, task_text=task, dimensions=_dims,
                weights={d: 1.0 for d in _dims},
                result={"verdict": verdict, "answers": {}, "confidence": 0.5,
                        "dim_confidence": {}, "emotion": {}, "curiosity": {}},
                complexity="simple",
            )
        except Exception: pass

        try:
            result = subprocess.run(
                ["codex", "--print", task],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            actual_result = result.stdout[:2000] if result.stdout else ""
            if not actual_result:
                actual_result = result.stderr[:500] if result.stderr else "(no output)"
            outcome_score = 1.0 if result.returncode == 0 else 0.3
        except FileNotFoundError:
            actual_result = "codex not found in PATH (安装: npm install -g @openai/codex)"
            outcome_score = 0.0
        except subprocess.TimeoutExpired:
            actual_result = "Codex timed out (60s)"
            outcome_score = 0.5
        except Exception as e:
            actual_result = f"Codex error: {e}"
            outcome_score = 0.0

        return {
            "execution_id": exec_id, "chain_id": chain_id,
            "channel": "codex", "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": outcome_score, "score": outcome_score,
            "timestamp": datetime.now().isoformat(),
        }

    # 统一入口 ─────────────────────────────────────────────────────────────
    def execute(self, task: str, verdict: str = "",
                channel: str = "auto", **kwargs) -> Dict[str, Any]:
        task_lower = task.lower()
        if channel == "auto":
            # P0: 优先用 IntentRouter 的 tool_route（everything-copilot-cli 路由模式）
            try:
                from judgment.intent_router import get_router
                router = get_router()
                tool_info = router.tool_route(task)
                if tool_info:
                    channel = tool_info[0]  # claude_code/hermes/codex
                    # codex channel is pending: tool not installed yet
                    if channel == "codex":
                        # Codex CLI 未安装，fallback 到 claude_code
                        channel = "claude_code"
            except Exception:
                pass
            # Fallback to keyword-based routing
            if channel == "auto":
                if any(kw in task_lower for kw in ["code", "bug", "refactor", "implement", "write", "review"]):
                    channel = "claude_code"
                elif any(kw in task_lower for kw in ["research", "search", "调研", "搜索"]):
                    channel = "hermes"
                else:
                    channel = "benchmark"

        if channel == "benchmark":
            result = self.execute_via_benchmark(task, expected_verdict=kwargs.get("expected_verdict", ""))
        elif channel == "hermes":
            result = self.execute_via_hermes(task, verdict)
        elif channel == "claude_code":
            result = self.execute_via_claude_code(task, verdict)
        elif channel == "codex":
            result = self.execute_via_codex(task, verdict)
        else:
            return {"error": f"Unknown channel: {channel}"}

        self._log_execution(result)
        self._verify_and_feedback(result)
        return result

    # 写入执行日志 ─────────────────────────────────────────────────────────
    def _log_execution(self, result: Dict):
        os.makedirs(os.path.dirname(_ACTION_LOG), exist_ok=True)
        with open(_ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # P2-8 修复：验证结果写回 evolver + experiences 表 ─────────────────────
    def _verify_and_feedback(self, result: Dict):
        """
        执行结果 → verify_outcome(闭环) + log_agent_behavior(experiences表)

        行为数据闭环：
          action_executor 拿到 outcome_score 后，
          同时写两个地方：
          1. verify_outcome() → evolver 权重更新（已有）
          2. log_agent_behavior() → experiences 表记录工具调用上下文（新增）
        """
        try:
            from judgment.closed_loop import verify_outcome
            chain_id = result.get("chain_id", "")
            if not chain_id: return

            # 已有：写 evolver（权重更新）
            verify_outcome(
                chain_id=chain_id,
                actual_action=result.get("action_description", ""),
                actual_consequence=result.get("actual_result", ""),
                outcome_score=result.get("outcome_score"),
                verifier=result.get("channel", "system"),
            )
        except Exception as e:
            print(f"[ActionExecutor] verify_outcome skip: {e}")

        # P2-8 新增：写 experiences 表（行为上下文）
        try:
            from judgment.behavior_logger import log_agent_behavior, ActionChannel

            # 映射 channel → ActionChannel enum
            ch = result.get("channel", "benchmark")
            try:
                action_channel = ActionChannel(ch)
            except ValueError:
                # benchmark 等未知 channel 映射为 judgment
                action_channel = ActionChannel.JUDGMENT

            # tool_calls: 从 execution_result 解析结构化信息
            # （action_executor 不保留原始 ToolCall dataclass，仅有 actual_result 文本）
            tool_calls = self._extract_tool_calls_from_result(result)

            log_agent_behavior(
                task_text=result.get("action_description", "").replace(f"[{ch.upper()}] ", ""),
                channel=action_channel,
                verdict=result.get("verdict", ""),
                confidence=result.get("outcome_score", 0.0),
                chain_id=chain_id,
                tool_calls=tool_calls,
                execution_result=result.get("actual_result", "")[:1000],
                perception_summary="",  # benchmark/hermes/claude_code 无感知摘要
                outcome_score=result.get("outcome_score", -1.0),
                user_id="default",
            )
        except Exception as e:
            print(f"[ActionExecutor] log_agent_behavior skip: {e}")

    def _extract_tool_calls_from_result(self, result: Dict) -> List:
        """
        从 result 字典提取 tool_calls 列表。

        action_executor 不知道 ToolCall dataclass 结构，
        但 actual_result 里可能包含结构化文本，尝试解析：

        格式（示例）："[Hermes] 搜索结果: xxx" 或 "[Claude Code] 已完成代码审查"
        解析为简化的 ToolCall 结构。
        """
        from dataclasses import dataclass
        from typing import List

        @dataclass
        class SimplifiedToolCall:
            tool_name: str
            arguments: dict
            result: str = ""

        channel = result.get("channel", "")
        action_desc = result.get("action_description", "")

        # 映射 channel → tool_name
        tool_name_map = {
            "hermes": "hermes_agent",
            "claude_code": "claude_code",
            "benchmark": "benchmark_validator",
        }
        tool_name = tool_name_map.get(channel, channel)

        actual = result.get("actual_result", "")
        if actual and len(actual) > 5:
            # actual_result 截断到合理长度
            result_text = actual[:500]
        else:
            result_text = "(无输出)"

        return [SimplifiedToolCall(
            tool_name=tool_name,
            arguments={"task": action_desc[:200], "channel": channel},
            result=result_text,
        )]

    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        if not os.path.exists(_ACTION_LOG): return []
        with open(_ACTION_LOG, encoding="utf-8") as f:
            lines = f.readlines()
        records = []
        for line in lines[-limit:]:
            try: records.append(json.loads(line.strip()))
            except Exception: continue
        return records[::-1]

    def get_channel_stats(self) -> Dict[str, Any]:
        history = self.get_execution_history(limit=1000)
        stats = {}
        for r in history:
            ch = r.get("channel", "unknown")
            if ch not in stats: stats[ch] = {"total": 0, "scores": []}
            stats[ch]["total"] += 1
            if "outcome_score" in r: stats[ch]["scores"].append(r["outcome_score"])
        for ch, data in stats.items():
            scores = data["scores"]
            data["avg_score"] = sum(scores)/len(scores) if scores else 0.0
            data["count"] = len(scores)
            del data["scores"]
        return stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python action_executor.py <task> [--channel=benchmark|hermes|claude_code]")
        print("       python action_executor.py --history")
        print("       python action_executor.py --stats")
        sys.exit(1)
    cmd = sys.argv[1]
    ae = ActionExecutor()
    if cmd == "--history":
        for r in ae.get_execution_history(): print(json.dumps(r, ensure_ascii=False))
    elif cmd == "--stats":
        print(json.dumps(ae.get_channel_stats(), ensure_ascii=False, indent=2))
    else:
        ch = "auto"
        for a in sys.argv[2:]:
            if a.startswith("--channel="): ch = a.split("=")[1]
        r = ae.execute(cmd, channel=ch)
        print(json.dumps(r, ensure_ascii=False, indent=2))