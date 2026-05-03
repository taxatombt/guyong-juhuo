#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doom_loop.py — Juhuo Doom Loop 检测器

来源：huggingface/ml-intern doom_loop.py 启发

检测 Agent 陷入反复调用同一工具的死循环。
核心思想：用 MD5 哈希检测"相同工具 + 相同参数 + 相同结果"签名重复。

关键设计（与 ml-intern 一致）：
- args_hash：归一化 JSON（sort_keys + 紧凑分隔符），防止 {"a":1,"b":2} vs {"b":2,"a":1} 逃逸
- result_hash：防止轮询被误判（相同参数 + 不同结果 = 不是 doom loop）
- lookback 窗口：只看最近 N 条消息，避免老历史干扰

注入恢复提示（与 ml-intern 一致）：
- 检测到 → 返回纠正提示，注入到 context 让 LLM 自我修正
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────────
DOOM_LOOP_THRESHOLD = 3       # 连续 N 次相同签名 → doom loop
LOOKBACK_WINDOW = 40          # 只看最近 N 条消息
MALFORMED_THRESHOLD = 2        # 连续 N 次 malformed args → 强制换策略

# ── 数据结构 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ToolCallSignature:
    """工具调用签名（哈希版，不可变可哈希）"""
    name: str
    args_hash: str
    result_hash: Optional[str] = None  # None = 无结果（调用尚未返回）


@dataclass
class DoomLoopReport:
    detected: bool
    tool_name: str | None = None
    streak: int = 0
    recovery_prompt: str | None = None


# ── 核心函数 ──────────────────────────────────────────────────────

def _normalize_args(args_str: str) -> str:
    """
    归一化工具参数字符串，用于哈希。

    LLMs 可能产生语义相同但格式不同的 JSON：
    {"a": 1, "b": 2} vs {"b": 2, "a": 1}
    {"a":1} vs {"a": 1}

    解析后重新序列化（sort_keys + 紧凑分隔符），确保等价形式产生相同哈希。
    失败时返回原始字符串（不会 raise）。
    """
    if not args_str:
        return ""
    try:
        return json.dumps(json.loads(args_str), sort_keys=True, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return args_str


def _hash_args(args_str: str) -> str:
    """返回参数字符串的 MD5 前 12 位哈希。"""
    return hashlib.md5(_normalize_args(args_str).encode()).hexdigest()[:12]


def _hash_result(result_str: str) -> str:
    """返回结果字符串的 MD5 前 12 位哈希。"""
    if not result_str:
        return ""
    return hashlib.md5(str(result_str).encode()).hexdigest()[:12]


def extract_tool_signatures(messages: list) -> list[ToolCallSignature]:
    """
    从消息列表中提取工具调用签名（只看最近 lookback 条）。

    支持两种格式的消息：
    1. dict 格式：{"role": "assistant", "tool_calls": [...]}
    2. 对象格式：有 .role / .tool_calls 属性的对象（litellm.Message）

    Args:
        messages: 消息列表（dict 或对象）
        lookback: 只看最近 N 条

    Returns:
        ToolCallSignature 列表（按出现顺序）
    """
    signatures = []
    recent = messages[-LOOKBACK_WINDOW:] if len(messages) > LOOKBACK_WINDOW else messages

    for idx, msg in enumerate(recent):
        # 统一：支持 dict 和对象两种格式
        if isinstance(msg, dict):
            role = msg.get("role", "")
            tool_calls = msg.get("tool_calls", None)
        else:
            role = getattr(msg, "role", "") or ""
            tool_calls = getattr(msg, "tool_calls", None) or []

        if role != "assistant" or not tool_calls:
            continue

        for tc in tool_calls:
            # 兼容 dict 和对象格式
            if isinstance(tc, dict):
                fn = tc.get("function", {}) or {}
                name = fn.get("name", "") or ""
                args_str = fn.get("arguments", "") or ""
            else:
                fn = getattr(tc, "function", None) or getattr(tc, "name", None)
                if fn is None:
                    continue
                name = getattr(fn, "name", "") or ""
                args_str = getattr(fn, "arguments", "") or ""

            if not name:
                continue

            args_hash = _hash_args(args_str)

            # 查找紧跟的工具结果
            result_hash = None
            for follow in recent[idx + 1:]:
                if isinstance(follow, dict):
                    follow_role = follow.get("role", "")
                    follow_content = follow.get("content", "")
                else:
                    follow_role = getattr(follow, "role", "") or ""
                    follow_content = getattr(follow, "content", "") or ""

                if follow_role == "tool":
                    result_hash = _hash_result(follow_content)
                    break  # 只取最近一个工具结果

            signatures.append(ToolCallSignature(
                name=name,
                args_hash=args_hash,
                result_hash=result_hash,
            ))

    return signatures


def check_doom_loop(messages: list) -> DoomLoopReport:
    """
    检测 doom loop：相同工具 + 相同参数 + 相同结果 连续出现。

    Returns:
        DoomLoopReport: detected=True 时附 streak 和 recovery_prompt
    """
    signatures = extract_tool_signatures(messages)
    if len(signatures) < DOOM_LOOP_THRESHOLD:
        return DoomLoopReport(detected=False)

    # 倒序扫描，找连续相同签名
    streak_tool: str | None = None
    streak = 0
    streak_with_result = 0  # 带结果的连续次数

    for sig in reversed(signatures):
        if sig.name != streak_tool:
            # 新工具，重置
            streak_tool = sig.name
            streak = 1
            streak_with_result = 1 if sig.result_hash else 0
            continue

        streak += 1

        if sig.result_hash:
            streak_with_result += 1

        if streak >= DOOM_LOOP_THRESHOLD and streak_with_result >= DOOM_LOOP_THRESHOLD:
            # 连续 3+ 次相同调用（含结果），判定为 doom loop
            recovery = (
                "[SYSTEM: Doom Loop 检测 — 你陷入了重复调用的死循环。]\n"
                f"工具 '{streak_tool}' 被连续调用 {streak} 次，但结果没有变化。\n"
                "请立即改变策略：\n"
                "  1. 停止重试相同操作\n"
                "  2. 尝试不同的方法解决问题\n"
                "  3. 如果需要等待某个条件完成，用不同方式检查（如读日志而非重复读同一文件）\n"
                "  4. 如果确认没有进展，直接告诉用户当前困境，请求人工介入"
            )
            return DoomLoopReport(
                detected=True,
                tool_name=streak_tool,
                streak=streak,
                recovery_prompt=recovery,
            )

    return DoomLoopReport(detected=False)


# ── Malformed Args 检测 ────────────────────────────────────────────

_MALFORMED_PREFIX = "ERROR: Tool call to '"
_MALFORMED_SUFFIX = "' had malformed JSON arguments"


def _extract_malformed_tool_name(content: str) -> str | None:
    """从 malformed tool result 内容中提取工具名。"""
    if not content.startswith(_MALFORMED_PREFIX):
        return None
    end = content.find(_MALFORMED_SUFFIX, len(_MALFORMED_PREFIX))
    if end == -1:
        return None
    return content[len(_MALFORMED_PREFIX):end]


def detect_malformed_tool(args_str: str) -> tuple[bool, str | None]:
    """
    检测参数字符串是否是 malformed JSON。

    Returns:
        (is_malformed, error_message)
    """
    if not args_str:
        return False, None

    # 字符串类型的 args → malformed（应该是 dict）
    if isinstance(args_str, str):
        try:
            json.loads(args_str)
        except (json.JSONDecodeError, TypeError, ValueError):
            return True, "参数必须是 JSON 对象，不能是字符串"
        return False, None

    # 非 dict 类型的 args → malformed
    if not isinstance(args_str, dict):
        return True, f"参数类型错误：期望 dict，实际 {type(args_str).__name__}"

    return False, None


def detect_repeated_malformed(messages: list, threshold: int = MALFORMED_THRESHOLD) -> str | None:
    """
    检测连续多次同样的工具参数格式错误。

    扫描消息列表尾部，找连续相同工具的 malformed result。
    连续 threshold 次以上 → 返回工具名。

    Args:
        messages: 消息列表
        threshold: 连续次数阈值（默认 2）

    Returns:
        工具名 或 None
    """
    if threshold <= 0:
        return None

    recent = messages[-LOOKBACK_WINDOW:] if len(messages) > LOOKBACK_WINDOW else messages
    streak_tool: str | None = None
    streak = 0

    for item in reversed(recent):
        if isinstance(item, dict):
            role = item.get("role", "")
            content = item.get("content", "")
        else:
            role = getattr(item, "role", "") or ""
            content = getattr(item, "content", "") or ""

        if role != "tool":
            continue

        malformed = _extract_malformed_tool_name(content)
        if malformed is None:
            break  # 不是 malformed result，停止扫描

        if streak_tool is None:
            streak_tool = malformed
            streak = 1
        elif malformed == streak_tool:
            streak += 1
        else:
            break  # 不同工具，停止

        if streak >= threshold:
            return streak_tool

    return None


def get_malformed_recovery_prompt(tool_name: str) -> str:
    """返回针对特定工具的 malformed args 恢复提示。"""
    return (
        f"[SYSTEM: 重复参数格式错误 — 工具 '{tool_name}' 连续产生 malformed JSON 参数。]\n"
        "请立即停止使用相同格式的参数。解决建议：\n"
        "  1. 简化参数：减少参数量，每个参数单独传入\n"
        "  2. 检查 JSON 格式：确保双引号、中括号配对\n"
        "  3. 大内容用 bash heredoc 或分批写入，不要一次传大段文本\n"
        "  4. 使用 Python 脚本生成参数，而不是手动拼接字符串"
    )


# ── 单元测试 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Test 1: 归一化哈希
    a = '{"a": 1, "b": 2}'
    b = '{"b": 2, "a": 1}'
    ha, hb = _hash_args(a), _hash_args(b)
    assert ha == hb, f"归一化失败：{ha} != {hb}"
    print("✅ Test 1: 归一化哈希 OK")

    # Test 2: doom loop 检测
    messages = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]},
        {"role": "tool", "content": "file1"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]},
        {"role": "tool", "content": "file1"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]},
        {"role": "tool", "content": "file1"},
    ]
    report = check_doom_loop(messages)
    assert report.detected, "Doom loop 未检测到"
    assert report.tool_name == "bash"
    print(f"✅ Test 2: Doom loop 检测 OK (tool={report.tool_name}, streak={report.streak})")

    # Test 3: 不同结果不算 doom loop
    messages_ok = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]},
        {"role": "tool", "content": "file1"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]},
        {"role": "tool", "content": "file2"},  # 不同结果
    ]
    report_ok = check_doom_loop(messages_ok)
    assert not report_ok.detected, "不同结果误判为 doom loop"
    print("✅ Test 3: 不同结果不算 doom loop OK")

    # Test 4: malformed 检测
    content = "ERROR: Tool call to 'write_file' had malformed JSON arguments"
    name = _extract_malformed_tool_name(content)
    assert name == "write_file", f"malformed 工具名提取失败：{name}"
    print("✅ Test 4: Malformed 工具名提取 OK")

    print("\n所有测试通过 ✅")
