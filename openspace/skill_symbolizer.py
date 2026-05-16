# ─────────────────────────────────────────────────────────────────────────────
# skill_symbolizer.py — 工具日志符号化（TencentDB-Agent-Memory 启发）
#
# 来源：Tencent/TencentDB-Agent-Memory 的 Mermaid 符号压缩设计
# 文档：workspace_tools/tencentdb-agent-memory/SKILL.md
#
# 核心理念：原始 tool logs 体积大，塞进 LLM 会浪费大量 token。
#          压缩成紧凑的 Mermaid 符号，token 减少 61%，成功率提升 51%。
#
# 原理：工具调用格式固定 → 可逆映射到符号
#   tool_call(name, args) → [!category:short_name]
#   恢复时反向查表即可
#
# 符号格式：
#   [!action]     执行类：写文件、发送消息、修改配置
#   [→url]        跳转类：打开浏览器、访问API
#   [?query]      搜索/查询类：网络搜索、数据库查询
#   [📊]          分析/处理类：数据分析、格式化
#   [✓] / [✗]     成功/失败标记
#   [⏳]          等待/阻塞类：sleep、轮询
#   [🔗]          关联/链接类：建立关联、更新记忆
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# ── 工具 → 符号映射表 ────────────────────────────────────────────────────────

TOOL_SYMBOLS: Dict[str, str] = {
    # 文件操作
    "file_read":        "[!📄]",
    "file_write":       "[!💾]",
    "file_delete":      "[!🗑]",
    "file_copy":        "[!📋]",
    "file_glob":        "[!🔍]",
    "edit_file":        "[!✏]",
    "read_file":        "[!📖]",

    # 网络操作
    "browser_open":     "[→🌐]",
    "browser_click":    "[→🖱]",
    "browser_type":     "[→⌨]",
    "http_request":     "[→📡]",
    "send_request":     "[→📡]",
    "fetch_url":        "[→🔗]",

    # 搜索/查询
    "web_search":       "[?🔎]",
    "search":           "[?🔎]",
    "grep_search":       "[?🔎]",
    "query":            "[?❓]",

    # 分析/处理
    "analyze":          "[📊]",
    "summarize":        "[📊]",
    "parse":            "[📊]",
    "format":          "[📊]",

    # 执行结果
    "success":         "[✓]",
    "error":           "[✗]",
    "fail":            "[✗]",

    # 等待/轮询
    "sleep":           "[⏳]",
    "wait":            "[⏳]",
    "poll":            "[⏳]",
    "retry":           "[⏳]",

    # 记忆/关联
    "save_memory":     "[🔗💾]",
    "memory_search":   "[🔗🔎]",
    "record":          "[🔗]",
    "update":          "[🔗✏]",

    # 决策/判断
    "judge":           "[⚖]",
    "decide":          "[⚖]",
    "evaluate":       "[⚖]",

    # 通用
    "execute":         "[⚙]",
    "run":             "[⚙]",
    "call":            "[⚙]",
    "shell":           "[⚙]",
    "unknown":         "[?]",
}


TOOL_CATEGORIES: Dict[str, List[str]] = {
    "file":    ["file_read", "file_write", "file_delete", "file_copy", "file_glob", "edit_file", "read_file"],
    "network": ["browser_open", "browser_click", "browser_type", "http_request", "send_request", "fetch_url"],
    "search":  ["web_search", "search", "grep_search", "query"],
    "analyze": ["analyze", "summarize", "parse", "format"],
    "wait":    ["sleep", "wait", "poll", "retry"],
    "memory":  ["save_memory", "memory_search", "record", "update"],
    "judge":   ["judge", "decide", "evaluate"],
}


# ── 符号化 ──────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    tool_name: str
    args: Dict  # 只保留关键参数
    result: Optional[str] = None
    timestamp: Optional[datetime] = None
    success: bool = True


@dataclass
class SymbolizedSession:
    symbols: List[str]           # 符号序列
    tool_count: int              # 原始工具调用数
    compressed_count: int         # 压缩后符号数
    compression_ratio: float     # 压缩比
    key_findings: List[str]       # 关键发现（从结果中提取）
    errors: List[str]             # 错误记录


def symbolize_tool_call(tool_call: ToolCall) -> str:
    """
    把一个工具调用转成符号。

    策略：
    1. 查 TOOL_SYMBOLS 表，找到了直接返回
    2. 按 category 模糊匹配
    3. 最后兜底 [!unknown]
    """
    name = tool_call.tool_name

    # 直接命中
    if name in TOOL_SYMBOLS:
        symbol = TOOL_SYMBOLS[name]
    else:
        # 模糊匹配 category
        symbol = None
        for cat, names in TOOL_CATEGORIES.items():
            if name in names:
                # 取第一个作为 category 代表
                symbol = TOOL_SYMBOLS.get(names[0], "[!]")
                break
        if symbol is None:
            # 兜底：取工具名前缀
            prefix = name.split("_")[0]
            symbol = f"[!{prefix}]"

    # 加参数提示（保留关键信息，截断噪声）
    key_args = _extract_key_args(tool_call.tool_name, tool_call.args)
    if key_args:
        symbol += f" {key_args}"

    # 状态标记
    if not tool_call.success:
        symbol = symbol.replace("]", " ⚠]")

    return symbol


def _extract_key_args(tool_name: str, args: Dict) -> str:
    """
    从工具参数中提取关键信息，生成紧凑提示。
    只保留有辨识度的信息，丢弃默认值和噪声。
    """
    if not args:
        return ""

    # 常见有意义的参数
    key_params = {
        "file_write":   ["path", "file_path"],
        "edit_file":    ["path", "file_path", "new_text"],
        "read_file":    ["path", "file_path"],
        "browser_open": ["url"],
        "http_request": ["url", "method"],
        "search":       ["query", "q", "pattern"],
        "grep_search":  ["pattern", "path"],
        "shell":        ["command", "cmd"],
        "execute":      ["command", "code"],
    }

    relevant = key_params.get(tool_name, ["path", "url", "query", "name", "target"])
    fragments = []

    for k in relevant:
        if k in args:
            v = str(args[k])
            # 截断过长的值
            if len(v) > 30:
                v = v[:27] + "..."
            fragments.append(f"{k}={v}")

    # 最多保留2个片段
    return " ".join(fragments[:2])


def symbolize_session(tool_calls: List[ToolCall]) -> SymbolizedSession:
    """
    把一组工具调用符号化，返回压缩结果。

    输出格式：
    [!💾 path=main.py] [!📄] [!→🌐 url=github.com] [✓] [!📖]
    """
    symbols = []
    errors = []
    key_findings = []

    for tc in tool_calls:
        sym = symbolize_tool_call(tc)
        symbols.append(sym)
        if not tc.success:
            errors.append(sym)
        # 从成功结果里提取关键发现
        if tc.success and tc.result:
            finding = _extract_finding(tc.tool_name, tc.result)
            if finding:
                key_findings.append(finding)

    total = len(tool_calls)
    compressed = len(symbols)

    return SymbolizedSession(
        symbols=symbols,
        tool_count=total,
        compressed_count=compressed,
        compression_ratio=compressed / total if total else 1.0,
        key_findings=key_findings,
        errors=errors,
    )


def _extract_finding(tool_name: str, result: str) -> Optional[str]:
    """
    从工具结果中提取关键发现。
    简单实现：检测关键词模式。
    """
    if not result:
        return None

    # 截断
    result = result.strip()[:200]

    if "error" in result.lower() or "failed" in result.lower():
        return None  # 错误已在 errors 里

    # 成功模式
    if tool_name == "file_write" and "wrote" in result.lower():
        return f"[✓ wrote]"
    if tool_name == "browser_open" and ("opened" in result.lower() or "navigated" in result.lower()):
        return f"[✓ opened]"
    if tool_name == "execute" or tool_name == "shell":
        if "done" in result.lower() or "ok" in result.lower():
            return f"[✓ done]"

    return None


def session_to_mermaid(tool_calls: List[ToolCall]) -> str:
    """
    生成 Mermaid 格式的时序图。
    用于日志记录和可视化。
    """
    lines = ["```mermaid", "sequenceDiagram"]

    for i, tc in enumerate(tool_calls):
        sym = symbolize_tool_call(tc)
        role = "Agent" if i % 2 == 0 else "System"
        note = f'Note over {role}: {sym}'
        lines.append(note)

    lines.append("```")
    return "\n".join(lines)


# ── 反符号化（调试用）───────────────────────────────────────────────────────

def desymbolize(symbol: str) -> str:
    """把符号还原为可读描述。"""
    # 简单实现：从符号中提取工具类型
    m = re.match(r"\[([!?→?📊⏳🔗⚖⚙])(.*?)\]", symbol)
    if not m:
        return symbol
    icon, rest = m.groups()
    descriptions = {
        "!": "执行操作",
        "→": "访问网络",
        "?": "查询搜索",
        "📊": "分析处理",
        "⏳": "等待",
        "🔗": "关联记忆",
        "⚖": "决策判断",
        "⚙": "系统执行",
    }
    return f"{descriptions.get(icon, icon)}{rest}"