#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_test.py — Juhuo 自检系统

启动前检查：
1. Python 版本
2. 依赖包
3. API Key 配置
4. 目录权限
5. 数据库连接
6. LLM 连通性
"""

from __future__ import annotations
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import sys
import importlib

from judgment.logging_config import get_logger

log = get_logger("juhuo.self_test")


@dataclass
class CheckResult:
    name: str
    status: str  # pass / fail / warn
    message: str
    details: str = ""


class SelfTest:
    """自检器"""
    
    def __init__(self):
        self.results: List[CheckResult] = []
    
    def check(self, name: str, test_func) -> CheckResult:
        """运行单个检查"""
        try:
            result = test_func()
            self.results.append(result)
            return result
        except Exception as e:
            r = CheckResult(name, "fail", str(e))
            self.results.append(r)
            return r
    
    def check_python_version(self) -> CheckResult:
        """检查 Python 版本"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 10:
            return CheckResult("Python 版本", "pass", f"{version.major}.{version.minor}.{version.micro}")
        return CheckResult("Python 版本", "fail", f"{version.major}.{version.minor} (需要 3.10+)")
    
    def check_dependencies(self) -> CheckResult:
        """检查依赖包"""
        required = ["flask", "yaml", "openai", "requests", "dotenv"]
        missing = []
        for pkg in required:
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append(pkg)
        
        if missing:
            return CheckResult("依赖包", "fail", f"缺少: {', '.join(missing)}")
        return CheckResult("依赖包", "pass", "全部安装")
    
    def check_api_keys(self) -> CheckResult:
        """检查 API Key"""
        import os
        keys = {
            "MINIMAX_API_KEY": os.environ.get("MINIMAX_API_KEY"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        }
        configured = [k for k, v in keys.items() if v]
        
        if configured:
            masked = [f"{k[:4]}...{k[-4:]}" for k in configured]
            return CheckResult("API Keys", "pass", f"已配置: {', '.join(masked)}")
        return CheckResult("API Keys", "fail", "未配置任何 API Key", "运行 juhuo config init")
    
    def check_data_dirs(self) -> CheckResult:
        """检查数据目录"""
        dirs = [
            Path.home() / ".juhuo",
            Path(__file__).parent.parent / "data",
        ]
        missing = []
        for d in dirs:
            if not d.exists():
                try:
                    d.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    missing.append(f"{d}: {e}")
        
        if missing:
            return CheckResult("数据目录", "warn", f"部分目录异常: {missing}")
        return CheckResult("数据目录", "pass", "正常")
    
    def check_llm_connectivity(self) -> CheckResult:
        """检查 LLM 连通性"""
        import os
        api_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            return CheckResult("LLM 连通性", "fail", "无 API Key")
        
        try:
            # 简单测试
            import requests
            # MiniMax test
            if os.environ.get("MINIMAX_API_KEY"):
                resp = requests.get(
                    "https://api.minimax.chat/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                if resp.status_code == 200:
                    return CheckResult("LLM 连通性", "pass", "MiniMax 连接正常")
            return CheckResult("LLM 连通性", "warn", "未测试到可用端点")
        except Exception as e:
            return CheckResult("LLM 连通ivity", "fail", str(e))
    
    def check_database(self) -> CheckResult:
        """检查数据库"""
        try:
            from causal_memory.causal_chain import init_db
            init_db()
            return CheckResult("数据库", "pass", "SQLite 正常")
        except Exception as e:
            return CheckResult("数据库", "fail", str(e))
    
    def run_all(self) -> Tuple[bool, List[CheckResult]]:
        """运行全部检查"""
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_api_keys,
            self.check_data_dirs,
            self.check_database,
            self.check_llm_connectivity,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.results.append(CheckResult(check.__name__, "fail", str(e)))
        
        passed = sum(1 for r in self.results if r.status == "pass")
        failed = sum(1 for r in self.results if r.status == "fail")
        warns = sum(1 for r in self.results if r.status == "warn")
        
        all_passed = failed == 0
        
        return all_passed, self.results
    
    def format_results(self, all_passed: bool, results: List[CheckResult]) -> str:
        """格式化结果"""
        lines = [
            "\n" + "="*50,
            "🔍 Juhuo Self-Test",
            "="*50,
        ]
        
        for r in results:
            icon = "✅" if r.status == "pass" else "❌" if r.status == "fail" else "⚠️"
            lines.append(f"{icon} {r.name}: {r.message}")
            if r.details:
                lines.append(f"   {r.details}")
        
        lines.append("-"*50)
        
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        warns = sum(1 for r in results if r.status == "warn")
        
        lines.append(f"结果: {passed} 通过 | {warns} 警告 | {failed} 失败")
        
        if all_passed:
            lines.append("✅ 系统就绪，可以启动!")
        else:
            lines.append("❌ 存在失败项，请修复后再试")
        
        lines.append("="*50)
        return "\n".join(lines)


def run_self_test() -> bool:
    """运行自检"""
    test = SelfTest()
    all_passed, results = test.run_all()
    print(test.format_results(all_passed, results))
    return all_passed


if __name__ == "__main__":
    success = run_self_test()
    sys.exit(0 if success else 1)
