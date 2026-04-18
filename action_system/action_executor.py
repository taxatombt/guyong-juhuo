#!/usr/bin/env python3
# action_system/action_executor.py
"""
Judgment → Action → Execution → Verification 完整闭环

三个执行通道：
1. benchmark: GDPVal ground truth 验证（无需真实行动）
2. hermes: 调用本地 Hermes agent 执行真实任务
3. claude_code: 委托 Claude Code 处理编程任务

每个通道执行后 → verify_outcome() → evolver

使用方式：
    executor = ActionExecutor()
    
    # 通道1: Benchmark 验证（立即）
    result = executor.execute_via_benchmark("要不要辞职创业？")
    print(result["score"])  # 0.0~1.0
    
    # 通道2: Hermes 执行（真实任务）
    result = executor.execute_via_hermes(
        task="帮我调研一下新能源行业的发展现状",
        verdict="建议先做调研再决定"
    )
    
    # 通道3: Claude Code（编程任务）
    result = executor.execute_via_claude_code(
        task="review这段代码",
        verdict="值得做"
    )
    
    # 查看执行历史
    executor.get_execution_history()
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

# ── 路径配置 ────────────────────────────────────────────────────────────────
_SELF_DIR = Path(__file__).parent
_ACTION_LOG = _SELF_DIR.parent / "data" / "actions" / "execution_log.jsonl"
_EVOLUTIONS_DIR = _SELF_DIR.parent / "data" / "evolutions"
os.makedirs(os.path.dirname(_ACTION_LOG), exist_ok=True)

# ── Dataclass ───────────────────────────────────────────────────────────────
@dataclass
class ExecutionResult:
    """一次执行的结果"""
    execution_id: str
    chain_id: str              # 对应 judgment snapshot
    channel: str               # "benchmark" | "hermes" | "claude_code"
    verdict: str               # 原始判决
    action_description: str     # 执行了什么
    actual_result: str         # 实际结果（执行输出）
    outcome_score: float       # 0.0~1.0
    execution_time_ms: float
    timestamp: str
    metadata: Dict[str, Any]

    def to_dict(self):
        d = asdict(self)
        d["timestamp"] = self.timestamp
        return d


# ── 主执行器 ────────────────────────────────────────────────────────────────
class ActionExecutor:
    """
    统一执行入口：judgment verdict → 行动计划 → 执行 → 验证
    
    设计原则：
    - 不阻塞：执行在后台，通过日志异步记录
    - 弱耦合：每个通道独立，可单独替换
    - 可验证：执行结果自动写 outcome_predictions
    """

    def __init__(self):
        self._juhuo_dir = _SELF_DIR.parent

    # ── 通道1: Benchmark ──────────────────────────────────────────────────
    def execute_via_benchmark(self, task: str, expected_verdict: str = "") -> Dict[str, Any]:
        """
        用 GDPVal benchmark 验证判断质量。
        
        直接拿 verdict 和 ground truth 比，不需要真实执行。
        用于快速验证判断准确率。
        
        Args:
            task: 判断任务
            expected_verdict: ground truth（可选，不填则从 DEFAULT_CASES 查）
        
        Returns:
            {
                "execution_id": "bench_xxx",
                "chain_id": "bench_xxx",
                "channel": "benchmark",
                "verdict": "...",
                "action_description": "与 benchmark expected 对比",
                "actual_result": "match_score: 0.7",
                "outcome_score": 0.7,
                "score": 0.7,  # 兼容
                "match": True/False,
                "expected": "...",
                "benchmark_case": "b001",
            }
        """
        exec_id = f"bench_{int(time.time()*1000)}"
        
        # 动态 import 避免循环依赖
        try:
            import sys
            sys.path.insert(0, str(self._juhuo_dir))
            from judgment.benchmark import Benchmark, DEFAULT_CASES
            
            # 找 ground truth
            expected = expected_verdict
            case_id = None
            if not expected:
                for case in DEFAULT_CASES:
                    if case.task == task:
                        expected = case.expected
                        case_id = case.id
                        break
            
            if not expected:
                return {
                    "execution_id": exec_id,
                    "channel": "benchmark",
                    "outcome_score": 0.0,
                    "score": 0.0,
                    "error": "No ground truth found for this task",
                }
            
            # 运行判断（MiniMax 需要 API key，跳过）
            from judgment.router import check10d_run
            result = check10d_run(task)
            verdict = result.get("verdict", "")
            chain_id = result.get("meta", {}).get("chain_id", exec_id)
            
            # 计算匹配分
            bm = Benchmark()
            score = bm._calc_match(verdict, expected)
            
            return {
                "execution_id": exec_id,
                "chain_id": chain_id,
                "channel": "benchmark",
                "verdict": verdict,
                "action_description": f"Benchmark对比: verdict vs expected",
                "actual_result": f"match_score={score:.3f}",
                "outcome_score": score,
                "score": score,
                "match": score >= 0.5,
                "expected": expected,
                "benchmark_case": case_id,
                "timestamp": datetime.now().isoformat(),
            }
        except ImportError as e:
            return {
                "execution_id": exec_id,
                "channel": "benchmark",
                "outcome_score": 0.0,
                "error": f"Import error: {e}",
            }

    # ── 通道2: Hermes ───────────────────────────────────────────────────
    def execute_via_hermes(self, task: str, verdict: str = "") -> Dict[str, Any]:
        """
        调用本地 Hermes agent 执行任务。
        
        Hermes 路径：~/.openclaw/workspace/hermes
        通过 copaw agents chat 发送任务。
        
        Args:
            task: 任务描述（judgment 的 task_text）
            verdict: 判决建议
        
        Returns:
            execution result with outcome_score
        """
        exec_id = f"hermes_{int(time.time()*1000)}"
        chain_id = f"hermes_chain_{int(time.time()*1000)}"
        
        # 先用 judgment 生成 chain_id（如果 task 在 juhuo 有记录）
        try:
            from judgment.closed_loop import snapshot_judgment
            _dims = ["cognitive", "economic", "temporal"]
            snapshot_judgment(
                chain_id=chain_id,
                task_text=task,
                dimensions=_dims,
                weights={d: 1.0 for d in _dims},
                result={"verdict": verdict, "answers": {}, "confidence": 0.5,
                        "dim_confidence": {}, "emotion": {}, "curiosity": {}},
                complexity="complex",
            )
        except Exception:
            pass
        
        action_desc = f"Hermes执行: {task[:60]}"
        
        # 尝试通过 copaw agents chat 发送
        try:
            result = subprocess.run(
                ["copaw", "agents", "chat", "--to", "hermes", "--message", task],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            actual_result = result.stdout[:2000] if result.stdout else ""
            if not actual_result:
                actual_result = result.stderr[:500] if result.stderr else "(no output)"
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
            "execution_id": exec_id,
            "chain_id": chain_id,
            "channel": "hermes",
            "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": outcome_score,
            "score": outcome_score,
            "timestamp": datetime.now().isoformat(),
        }

    # ── 通道3: Claude Code ───────────────────────────────────────────────
    def execute_via_claude_code(self, task: str, verdict: str = "") -> Dict[str, Any]:
        """
        委托 Claude Code 处理编程任务。
        
        通过 claude CLI 或 codex CLI 执行。
        """
        exec_id = f"cc_{int(time.time()*1000)}"
        chain_id = f"cc_chain_{int(time.time()*1000)}"
        action_desc = f"Claude Code执行: {task[:60]}"
        
        try:
            result = subprocess.run(
                ["claude", "--print", task],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            actual_result = result.stdout[:2000] if result.stdout else ""
            if not actual_result:
                actual_result = result.stderr[:500] if result.stderr else "(no output)"
            outcome_score = 1.0 if result.returncode == 0 else 0.3
        except FileNotFoundError:
            try:
                # 尝试 codex
                result = subprocess.run(
                    ["codex", task],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding="utf-8",
                    errors="replace",
                )
                actual_result = result.stdout[:2000] if result.stdout else ""
                outcome_score = 1.0 if result.returncode == 0 else 0.3
            except FileNotFoundError:
                actual_result = "claude/codex CLI not found"
                outcome_score = 0.0
        except subprocess.TimeoutExpired:
            actual_result = "Claude Code timed out (120s)"
            outcome_score = 0.5
        except Exception as e:
            actual_result = f"Claude Code error: {e}"
            outcome_score = 0.0

        return {
            "execution_id": exec_id,
            "chain_id": chain_id,
            "channel": "claude_code",
            "verdict": verdict,
            "action_description": action_desc,
            "actual_result": actual_result,
            "outcome_score": outcome_score,
            "score": outcome_score,
            "timestamp": datetime.now().isoformat(),
        }

    # ── 统一执行入口 ─────────────────────────────────────────────────────
    def execute(self, task: str, verdict: str = "",
                channel: str = "auto", **kwargs) -> Dict[str, Any]:
        """
        统一执行入口，自动选择通道。
        
        channel="auto": 根据任务类型自动选择
          - 编程相关 → claude_code
          - 调研/搜索 → hermes  
          - 其他 → benchmark（仅验证）
        """
        task_lower = task.lower()
        
        if channel == "auto":
            if any(kw in task_lower for kw in ["code", "bug", "refactor", "implement", "write", "review"]):
                channel = "claude_code"
            elif any(kw in task_lower for kw in ["research", "search", "调研", "搜索", "查"]):
                channel = "hermes"
            else:
                channel = "benchmark"
        
        if channel == "benchmark":
            result = self.execute_via_benchmark(task, expected_verdict=kwargs.get("expected_verdict", ""))
        elif channel == "hermes":
            result = self.execute_via_hermes(task, verdict)
        elif channel == "claude_code":
            result = self.execute_via_claude_code(task, verdict)
        else:
            return {"error": f"Unknown channel: {channel}"}
        
        # ── 写入执行日志 ─────────────────────────────────────────────────
        self._log_execution(result)
        
        # ── 验证结果写回 evolver ──────────────────────────────────────────
        self._verify_and_feedback(result)
        
        return result

    # ── 私有方法 ─────────────────────────────────────────────────────────
    def _log_execution(self, result: Dict):
        """写入执行日志"""
        os.makedirs(os.path.dirname(_ACTION_LOG), exist_ok=True)
        with open(_ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def _verify_and_feedback(self, result: Dict):
        """执行结果 → verify_outcome → evolver"""
        try:
            from judgment.closed_loop import verify_outcome
            chain_id = result.get("chain_id", "")
            if not chain_id:
                return
            
            verify_outcome(
                chain_id=chain_id,
                actual_action=result.get("action_description", ""),
                actual_consequence=result.get("actual_result", ""),
                outcome_score=result.get("outcome_score"),
                verifier=result.get("channel", "system"),
            )
        except Exception as e:
            print(f"[ActionExecutor] verify feedback skip: {e}")

    # ── 查询接口 ─────────────────────────────────────────────────────────
    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """读取执行历史"""
        if not os.path.exists(_ACTION_LOG):
            return []
        with open(_ACTION_LOG, encoding="utf-8") as f:
            lines = f.readlines()
        
        records = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line.strip()))
            except Exception:
                continue
        return records[::-1]  # 最新的在前

    def get_channel_stats(self) -> Dict[str, Any]:
        """各通道执行统计"""
        history = self.get_execution_history(limit=1000)
        stats = {}
        for r in history:
            ch = r.get("channel", "unknown")
            if ch not in stats:
                stats[ch] = {"total": 0, "scores": []}
            stats[ch]["total"] += 1
            if "outcome_score" in r:
                stats[ch]["scores"].append(r["outcome_score"])
        
        for ch, data in stats.items():
            scores = data["scores"]
            data["avg_score"] = sum(scores) / len(scores) if scores else 0.0
            data["count"] = len(scores)
            del data["scores"]
        
        return stats


# ── CLI 入口 ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python action_executor.py <task> [--channel=benchmark|hermes|claude_code]")
        print("       python action_executor.py --history")
        print("       python action_executor.py --stats")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "--history":
        ae = ActionExecutor()
        for r in ae.get_execution_history():
            print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0)
    
    if cmd == "--stats":
        ae = ActionExecutor()
        stats = ae.get_channel_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        sys.exit(0)
    
    task = cmd
    channel = "benchmark"
    for a in sys.argv[2:]:
        if a.startswith("--channel="):
            channel = a.split("=", 1)[1]
    
    ae = ActionExecutor()
    result = ae.execute(task, channel=channel)
    print(json.dumps(result, ensure_ascii=False, indent=2))
