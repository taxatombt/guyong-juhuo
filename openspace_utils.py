#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openspace_utils.py — OpenSpace 推荐的工具函数，按优先级落地

P0:
  1. skill_id 格式: {name}__v{fix_version}_{hash}
  2. .skill_id sidecar 文件（同 SKILL.md 目录，持久化 ID）

P1:
  3. conversation_formatter 优先级截断（6级优先级）

P2:
  4. detect_patch_type() 自动识别 LLM 输出类型 (FULL/DIFF/PATCH)

P3:
  5. 简化版模糊匹配（中文友好，不依赖 Unicode 复杂处理）

参考: OpenSpace (HKUDS) 源码推荐实践
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# ─── P0: skill_id 格式 + .skill_id sidecar ──────────────────────

def generate_skill_id(skill_name: str, fix_version: int, content: str) -> str:
    """
    Generate skill_id in OpenSpace recommended format:
      {name}__v{fix_version}_{hash}

    Example:
      systematic-debugging__v2_8a3b2f1c
    """
    # 计算内容 hash (前 8 位足够)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    return f"{skill_name}__v{fix_version}_{content_hash}"


def read_skill_id(skill_dir: Path) -> Optional[str]:
    """Read persisted skill_id from .skill_id sidecar file"""
    sidecar = skill_dir / ".skill_id"
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").strip()
    return None


def write_skill_id(skill_dir: Path, skill_id: str):
    """Write skill_id to .skill_id sidecar file"""
    sidecar = skill_dir / ".skill_id"
    sidecar.write_text(skill_id + "\n", encoding="utf-8")
    # Add to .gitignore if not already there
    gitignore = skill_dir / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if ".skill_id" not in content:
            if not content.endswith("\n"):
                content += "\n"
            content += ".skill_id\n"
            gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text(".skill_id\n", encoding="utf-8")


def get_or_generate_skill_id(
    skill_dir: Path,
    skill_name: str,
    fix_version: int = 0,
    content: str = "",
) -> str:
    """Get existing skill_id from sidecar or generate new"""
    existing = read_skill_id(skill_dir)
    if existing:
        return existing
    if not content:
        # If no content provided, generate hash from skill name
        content_hash = hashlib.sha256(skill_name.encode("utf-8")).hexdigest()[:8]
        new_id = f"{skill_name}__v{fix_version}_{content_hash}"
    else:
        new_id = generate_skill_id(skill_name, fix_version, content)
    write_skill_id(skill_dir, new_id)
    return new_id


def parse_skill_id(skill_id: str) -> Optional[Tuple[str, int, str]]:
    """Parse skill_id into (name, fix_version, hash)"""
    # Format: name__vX_hash
    parts = skill_id.split("__")
    if len(parts) != 2:
        return None
    name = parts[0]
    rest = parts[1]
    if not rest.startswith("v"):
        return None
    v_part = rest.split("_")[0]
    hash_part = "_".join(rest.split("_")[1:])
    try:
        fix_version = int(v_part[1:])
    except ValueError:
        return None
    return (name, fix_version, hash_part)


# ─── P1: conversation_formatter 优先级截断 ──────────────────────

class PriorityLevel:
    """6优先级定义，对应 OpenSpace 优先级截断"""
    CRITICAL = 0    # 错误信息、用户指令、最终结论 → 绝对保留
    HIGH = 1        # 关键决策、验证结果 → 保留
    MEDIUM = 2      # 分析过程、中间步骤 → 截断靠后
    LOW = 3         # 调试输出、重复信息 → 优先截断
    VERY_LOW = 4    # 日志、冗长输出 → 尽早截断
    DEBUG = 5       # 临时调试信息 → 最先截断


class PriorityMessage:
    def __init__(self, priority: int, content: str, metadata: Optional[dict] = None):
        self.priority = priority
        self.content = content
        self.metadata = metadata or {}


class ConversationFormatter:
    """
    优先级截断对话压缩，用于 LLM 分析长对话
    越高优先级越保留，越低优先级越先被截断
    """
    def __init__(
        self,
        max_total_tokens: int = 16000,
        approx_tokens_per_line: int = 4,
    ):
        self.max_total_tokens = max_total_tokens
        self.approx_tokens_per_line = approx_tokens_per_line

    def format_conversation(
        self,
        messages: List[PriorityMessage],
    ) -> str:
        """Format and truncate by priority"""
        # Sort by priority ascending (critical first)
        sorted_msgs = sorted(messages, key=lambda m: m.priority)

        # Keep adding until we hit max
        lines = []
        current_tokens = 0
        truncated = 0

        for msg in sorted_msgs:
            msg_lines = msg.content.splitlines()
            msg_tokens = len(msg_lines) * self.approx_tokens_per_line

            if current_tokens + msg_tokens <= self.max_total_tokens:
                lines.append(msg.content)
                current_tokens += msg_tokens
            else:
                truncated += len(msg_lines)

        result = "\n\n".join(lines)
        if truncated > 0:
            result += f"\n\n[Truncated: {truncated} lower-priority lines omitted]"

        return result

    def format_from_plain(
        self,
        messages: List[Tuple[int, str]],
    ) -> str:
        """Take (priority, content) tuples and format"""
        pmsgs = [PriorityMessage(p, c) for p, c in messages]
        return self.format_conversation(pmsgs)


# ─── P2: detect_patch_type() ────────────────────────────────────

class PatchType:
    FULL = "FULL"       # Full file replacement
    DIFF = "DIFF"       # Unified diff format
    PATCH = "PATCH"     # Search/replace block patch (SR/current format)
    RAW = "RAW"         # Raw text, no patch structure


def detect_patch_type(content: str) -> str:
    """
    Detect patch type from LLM output:
    - FULL: entire file content
    - DIFF: unified diff (--- +++ lines)
    - PATCH: search/replace blocks (<<<<<<< SEARCH / ======= / >>>>>>> REPLACE)
    - RAW: raw text
    """
    content = content.strip()

    # Check for search/replace patch format (common in Claude Code / Kiro)
    if "<<<<<<< SEARCH" in content and "=======" in content and ">>>>>>> REPLACE" in content:
        return PatchType.PATCH

    # Check for unified diff
    lines = content.splitlines()
    diff_lines = 0
    for line in lines[:10]:
        if line.startswith("--- ") and "+++ " in line:
            diff_lines += 1
        if line.startswith("+++ "):
            diff_lines += 1
        if line.startswith("@@ "):
            diff_lines += 1
    if diff_lines >= 2:
        return PatchType.DIFF

    # Check if this is a full file (heuristic: looks like complete file)
    # If it's longer than 20 lines and has multiple imports/functions → likely full
    if len(lines) >= 10:
        has_import = any("import " in line for line in lines[:20])
        has_def = any(line.strip().startswith(("def ", "class ", "function ", "const ", "let ")) for line in lines[:20])
        if has_import or has_def:
            return PatchType.FULL

    # Check for markdown code block wrapping a full file
    if content.startswith("```") and content.endswith("```"):
        # Extract content inside
        inner = content.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        inner_lines = inner.splitlines()
        if len(inner_lines) >= 10:
            has_import = any("import " in line for line in inner_lines[:20])
            has_def = any(line.strip().startswith(("def ", "class ")) for line in inner_lines[:20])
            if has_import or has_def:
                return PatchType.FULL

    # Default to RAW
    return PatchType.RAW


# ─── P3: 简化版模糊匹配（中文友好）─────────────────────────────────

def simple_fuzzy_search(pattern: str, text: str, threshold: int = 3) -> int:
    """
    Simple fuzzy match for Chinese text.
    Returns number of mismatched characters.
    0 = exact match, lower = better.

    Uses simple Levenshtein distance (DP) but optimized for small patterns.
    If mismatches <= threshold → considered a match.

    Does NOT do Unicode normalization like OpenSpace (Chinese doesn't need it).
    """
    m, n = len(pattern), len(text)
    if m == 0:
        return 0
    if abs(m - n) > threshold:
        return threshold + 1

    # DP table
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pattern[i-1] == text[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],      # deletion
                    dp[i][j-1],      # insertion
                    dp[i-1][j-1],    # substitution
                )
                # Early exit if already over threshold
                if dp[i][j] > threshold and i == m:
                    return dp[i][j]

    return dp[m][n]


def find_best_match(pattern: str, candidates: List[str], max_mismatches: int = 3) -> Optional[Tuple[str, int]]:
    """Find best matching candidate, return (candidate, mismatches) or None"""
    best = None
    best_score = max_mismatches + 1

    for candidate in candidates:
        score = simple_fuzzy_search(pattern, candidate, max_mismatches)
        if score <= best_score and score <= max_mismatches:
            if score < best_score:
                best_score = score
                best = candidate

    if best is not None:
        return (best, best_score)
    return None


# ─── conversation_formatter 附加：action_log 格式化 ──────────────────

def format_action_log(
    records: List[Dict],
    max_tokens: int = 16000,
) -> str:
    """
    Format action_log entries with priority for LLM analysis
    Adapts to guyong-juhuo / CoPaw action_log format

    Priority mapping (OpenSpace original):
    - CRITICAL (0): User request / Final conclusion
    - HIGH (1): Tool calls / Errors / Execution Summary
    - MEDIUM (2): Tool success output
    - LOW (3): Debug / Verbose
    """
    cf = ConversationFormatter(max_total_tokens=max_tokens)
    priority_messages = []

    for rec in records:
        # Guess priority based on content
        if rec.get("is_user_request") or rec.get("is_final_conclusion"):
            priority = PriorityLevel.CRITICAL
        elif rec.get("error") is not None or rec.get("tool_call") or "Execution Summary" in str(rec.get("content", "")):
            priority = PriorityLevel.HIGH
        elif rec.get("success"):
            priority = PriorityLevel.MEDIUM
        else:
            priority = PriorityLevel.LOW

        content = str(rec.get("content", ""))
        if rec.get("timestamp"):
            content = f"[{rec['timestamp']}] {content}"
        priority_messages.append((priority, content))

    return cf.format_from_plain(priority_messages)


# ─── Helper: 输出结果说明 ────────────────────────────────────────

def get_implementation_summary() -> dict:
    """Return implementation summary for documentation"""
    return {
        "implemented": [
            "skill_id format {name}__v{fix_version}_{hash}",
            ".skill_id sidecar file with .gitignore entry",
            "conversation_formatter 6-level priority truncation",
            "format_action_log() for CoPaw/guyong-juhuo action_log",
            "detect_patch_type() for FULL/DIFF/PATCH/RAW",
            "simple_fuzzy_search (Chinese-friendly, no external dependencies)",
        ],
        "not_implemented": [
            "4-level complex fuzzy matching (OpenSpace seek_sequence), Chinese uncertain",
            "multi-parent derive (deferred to complex needs)",
            "full multi-file PATCH engine (900+ lines, overkill)",
            "fuzzy_match.py 6-level chain (depends on external lib)",
            "skill_ranker.py LLM-based ranking (deferred)",
        ],
        "priority": {
            "P0": "skill_id + sidecar",
            "P1": "conversation_formatter",
            "P2": "detect_patch_type",
            "P3": "simple fuzzy match",
        },
    }
