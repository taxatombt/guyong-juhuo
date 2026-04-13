#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_hook.py — 行动规划安全检查

集成来源：guyongt security_hook.py → action_system/
设计原则：
- 10种危险模式检测，行动规划前必查
- 返回 SecurityLevel 分级（CRITICAL/HIGH/MEDIUM/LOW/SAFE）

检测模式：
    eval() / new Function() / child_process.exec()
    innerHTML / dangerouslySetInnerHTML
    SQL拼接 / pickle反序列化
    os.system() / curl|wget | bash
    递归删除 rm -rf /

使用方式：
    from action_system.security_hook import SecurityHook, SecurityLevel

    hook = SecurityHook()
    findings = hook.check_code("subprocess.run(['rm', '-rf', '/'])")
    if findings:
        for f in findings:
            lines.append(f"  [{f.level_name}] {f.name} (L{f.line_number})")
            lines.append(f"    -> {f.detail}")
            lines.append(f"    -> {f.matched_text[:60]}")
        return "\n".join(lines):
            print(f"[{f.level_name}] {f.name}: {f.matched_text[:50]}")
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


class SecurityLevel:
    SAFE = -1
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3

    @staticmethod
    def name(level: int) -> str:
        return {-1: "SAFE", 0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}.get(level, "UNKNOWN")


_DANGEROUS_PATTERNS = [
    # 1: 动态代码执行
    {
        "id": "code_exec", "name": "代码执行", "level": SecurityLevel.CRITICAL,
        "patterns": [
            r"\beval\s*\(", r"\bexec\s*\(", r"new\s+Function\s*\(",
            r"child_process\s*\.\s*exec", r"os\.system\s*\(", r"os\.popen\s*\(",
            r"subprocess\s*\.\s*(run|call)\s*\([^)]*shell\s*=\s*True",
        ],
        "detail": "检测到动态代码执行，可能是命令注入"
    },
    # 2: 管道到Shell
    {
        "id": "pipe_bash", "name": "管道到Shell", "level": SecurityLevel.CRITICAL,
        "patterns": [
            r"curl\s+.*\|\s*(bash|sh|zsh|fish)",
            r"wget\s+.*\|\s*(bash|sh|zsh|fish)",
            r"\|\s*bash", r"\|\s*sh\s*-c",
        ],
        "detail": "管道到shell执行，可能被中间人注入恶意命令"
    },
    # 3: 递归删除
    {
        "id": "recursive_delete", "name": "递归删除", "level": SecurityLevel.CRITICAL,
        "patterns": [
            r"rm\s+-rf\s+/", r"rm\s+-rf\s+\*~", r"rm\s+-rf\s+\$",
            r"del\s+/f/s/q\s+\*", r"Remove-Item\s+-Recurse\s+-Force",
            r"rm\s+-\s*rf\s+\.", r"find\s+.*-delete",
        ],
        "detail": "递归删除或全局777权限，风险极高"
    },
    # 4: XSS
    {
        "id": "xss", "name": "XSS注入风险", "level": SecurityLevel.HIGH,
        "patterns": [
            r"innerHTML\s*=", r"outerHTML\s*=", r"dangerouslySetInnerHTML",
            r"\.html\s*\(", r"v-html\s*=",
        ],
        "detail": "直接HTML注入可能导致XSS攻击"
    },
    # 5: SQL注入
    {
        "id": "sql_injection", "name": "SQL注入", "level": SecurityLevel.HIGH,
        "patterns": [
            r'execute\s*\(\s*f["\'].*\%s',
            r'execute\s*\(\s*["\'].*\+.*["\']',
            r'cursor\.execute\s*\([^)]*\+',
        ],
        "detail": "SQL拼接容易注入，建议参数化查询"
    },
    # 6: 序列化危险
    {
        "id": "pickle", "name": "Pickle反序列化", "level": SecurityLevel.HIGH,
        "patterns": [
            r"pickle\.load\s*\(", r"pickle\.loads\s*\(",
            r"torch\.load\s*\(", r"yaml\.load\s*\(",
        ],
        "detail": "非可信来源的pickle反序列化可执行任意代码"
    },
    # 7: 环境变量注入
    {
        "id": "env_injection", "name": "环境变量注入", "level": SecurityLevel.MEDIUM,
        "patterns": [
            r"os\.environ\s*\[\s*['\"].*['\"]\s*\]\s*=",
        ],
        "detail": "环境变量注入可能改变程序行为"
    },
    # 8: 过度权限
    {
        "id": "chmod_777", "name": "过度权限", "level": SecurityLevel.MEDIUM,
        "patterns": [
            r"chmod\s+777", r"chmod\s+0o777", r"chmod\s+-R\s+777",
        ],
        "detail": "全局777权限可能导致文件被恶意利用"
    },
    # 9: 下载并执行
    {
        "id": "download_exec", "name": "下载并执行", "level": SecurityLevel.CRITICAL,
        "patterns": [
            r"wget\s+.*\s+-O\s+.*\|\s*",
            r"curl\s+.*\s+-o\s+.*chmod",
            r"Invoke-WebRequest.*\|.*iex",
        ],
        "detail": "下载并直接执行可能运行恶意代码"
    },
    # 10: 危险Git操作
    {
        "id": "git_dangerous", "name": "Git危险操作", "level": SecurityLevel.MEDIUM,
        "patterns": [
            r"git\s+filter-branch",
            r"git\s+push\s+--force",
            r"git\s+rebase\s+-i\s+HEAD~\d+",
        ],
        "detail": "不可逆的Git操作，可能丢失代码历史"
    },
]


@dataclass
class SecurityFinding:
    pattern_id: str
    name: str
    level: int
    detail: str
    matched_text: str
    line_number: Optional[int] = None

    @property
    def level_name(self) -> str:
        return SecurityLevel.name(self.level)

    def to_dict(self) -> dict:
        return {
            "id": self.pattern_id, "name": self.name,
            "level": self.level, "level_name": self.level_name,
            "detail": self.detail,
            "matched": self.matched_text[:80],
            "line": self.line_number,
        }


class SecurityHook:
    """
    行动规划安全检查钩子

    API：
        check_code(code: str) -> List[SecurityFinding]
        check_file(path: str) -> List[SecurityFinding]
        is_safe(code: str) -> bool
        highest_level(code: str) -> int
        summary(code: str) -> str
    """

    def __init__(self, min_level: int = SecurityLevel.LOW):
        self.min_level = min_level

    def check_code(self, code: str) -> List[SecurityFinding]:
        findings = []
        lines = code.split("\n")
        for line_no, line in enumerate(lines, 1):
            for pat in _DANGEROUS_PATTERNS:
                if pat["level"] < self.min_level:
                    continue
                for pattern in pat["patterns"]:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append(SecurityFinding(
                            pattern_id=pat["id"], name=pat["name"],
                            level=pat["level"], detail=pat["detail"],
                            matched_text=line.strip(), line_number=line_no,
                        ))
                        break
        return findings

    def check_file(self, path: str) -> List[SecurityFinding]:
        p = Path(path)
        if not p.exists():
            return []
        code = p.read_text(encoding="utf-8", errors="ignore")
        return self.check_code(code)

    def is_safe(self, code: str) -> bool:
        return len(self.check_code(code)) == 0

    def highest_level(self, code: str) -> int:
        findings = self.check_code(code)
        if not findings:
            return SecurityLevel.SAFE
        return max(f.level for f in findings)

    def summary(self, code: str) -> str:
        findings = self.check_code(code)
        if not findings:
            return "SAFE: No security issues detected"
        lines = [f"WARNING: Found {len(findings)} security issue(s):"]
        for f in findings:
            lines.append(f"  [{f.level_name}] {f.name} (L{f.line_number})")
            lines.append(f"    -> {f.detail}")
            lines.append(f"    -> {f.matched_text[:60]}")
        return "\n".join(lines)