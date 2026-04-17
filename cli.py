#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — Juhuo CLI

命令行工具：
- juhuo [task]        # 单次判断
- juhuo shell         # 交互模式
- juhuo web           # 启动 Web Console
- juhuo status         # 查看状态
- juhuo verdict       # verdict 管理
- juhuo config        # 配置管理
"""

import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from judgment.logging_config import get_logger
from judgment.pipeline import check10d_full, PipelineConfig, format_full_report
from judgment.self_model.belief import get_belief_status
from judgment.verdict_collector import get_verdict_stats, mark_verdict_correct, mark_verdict_wrong
from causal_memory.causal_chain import get_recent_chains, get_chain_detail
from config.env_loader import EnvVarLoader, create_env_template, JUHuo_USER_DIR, JUHuo_USER_ENV
from judgment.benchmark import Benchmark, run_benchmark

log = get_logger("juhuo.cli")


def cmd_judge(task: str, verbose: bool = False):
    """执行判断"""
    print(f"\n⚖️  正在分析: {task}\n")
    
    result = check10d_full(task)
    
    if verbose:
        print(format_full_report(result))
    else:
        print(f"→ 建议: {result.get('verdict', '无法判断')}")
        print(f"→ 置信度: {result.get('confidence', 0) * 100:.1f}%")
        print(f"→ Chain ID: {result.get('chain_id', '')}")


def cmd_shell():
    """交互模式"""
    print("\n" + "="*50)
    print("⚖️  Juhuo Interactive Shell")
    print("="*50)
    print("输入问题让 Juhuo 帮助判断")
    print("输入 quit / exit 退出\n")
    
    while True:
        try:
            task = input("问题> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见!")
            break
        
        if task.lower() in ("quit", "exit", "q"):
            print("再见!")
            break
        
        if not task:
            continue
        
        cmd_judge(task)


def cmd_status():
    """查看状态"""
    belief = get_belief_status()
    stats = get_verdict_stats()
    chains = get_recent_chains(limit=5)
    
    print("\n" + "="*50)
    print("📊 Juhuo 状态")
    print("="*50)
    
    print("\n【置信度状态】")
    for dim, info in belief.items():
        score = info.get("confidence", 0) * 100
        status = "🔴" if score < 50 else "🟡" if score < 70 else "🟢"
        print(f"  {status} {dim}: {score:.1f}%")
    
    print("\n【Verdict 统计】")
    print(f"  总判断数: {stats.get('total', 0)}")
    print(f"  正确数: {stats.get('correct', 0)}")
    print(f"  错误数: {stats.get('wrong', 0)}")
    if stats.get('total', 0) > 0:
        acc = stats['correct'] / stats['total'] * 100
        print(f"  准确率: {acc:.1f}%")
    
    print("\n【最近判断】")
    for chain in chains:
        cid = chain.get("chain_id", "")[:8]
        task = chain.get("task", "")[:40]
        verdict = chain.get("verdict", "")[:20]
        print(f"  [{cid}] {task}... → {verdict}")


def cmd_verdict(args):
    """Verdict 管理"""
    if args.action == "list":
        chains = get_recent_chains(limit=args.limit)
        print(f"\n【最近 {len(chains)} 条判断】\n")
        for chain in chains:
            cid = chain.get("chain_id", "")
            task = chain.get("task", "")[:50]
            verdict = chain.get("verdict", "")
            correct = chain.get("correct")
            mark = "✅" if correct == True else "❌" if correct == False else "❓"
            print(f"{mark} [{cid}] {task}...")
            print(f"    → {verdict}\n")
    
    elif args.action == "correct":
        mark_verdict_correct(args.chain_id)
        print(f"✅ 已标记为正确: {args.chain_id}")
    
    elif args.action == "wrong":
        mark_verdict_wrong(args.chain_id)
        print(f"❌ 已标记为错误: {args.chain_id}")
    
    elif args.action == "detail":
        detail = get_chain_detail(args.chain_id)
        if detail:
            print(format_full_report(detail))
        else:
            print(f"未找到: {args.chain_id}")


def cmd_config(args):
    """配置管理"""
    if args.action == "show":
        print(f"\n【Juhuo 配置】")
        print(f"  配置目录: {JUHuo_USER_DIR}")
        print(f"  环境文件: {JUHuo_USER_ENV}")
        print(f"  存在: {JUHuo_USER_ENV.exists()}")
        
        print("\n【环境变量】")
        for key in ["DEFAULT_PROVIDER", "DEFAULT_MODEL", "MINIMAX_API_KEY"]:
            val = os.environ.get(key, "(未设置)")
            if "API_KEY" in key and val != "(未设置)":
                val = val[:8] + "..."
            print(f"  {key}: {val}")
    
    elif args.action == "init":
        path = create_env_template()
        print(f"✅ 配置文件已创建: {path}")
        print("   请编辑文件填入 API Key")
    
    elif args.action == "edit":
        if JUHuo_USER_ENV.exists():
            os.startfile(JUHuo_USER_ENV) if sys.platform == "win32" else None
            print(f"已打开: {JUHuo_USER_ENV}")
        else:
            print("配置文件不存在，先运行: juhuo config init")


def main():
    parser = argparse.ArgumentParser(
        description="⚖️ Juhuo - Judgment System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="cmd", help="子命令")
    
    # judge
    judge_parser = subparsers.add_parser("judge", help="执行判断")
    judge_parser.add_argument("task", help="判断问题")
    judge_parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    
    # shell
    subparsers.add_parser("shell", help="交互模式")
    
    # web
    web_parser = subparsers.add_parser("web", help="启动 Web Console")
    web_parser.add_argument("--port", type=int, default=18768, help="端口")
    
    # status
    subparsers.add_parser("status", help="查看状态")
    
    # verdict
    verdict_parser = subparsers.add_parser("verdict", help="Verdict 管理")
    verdict_parser.add_argument("action", choices=["list", "correct", "wrong", "detail"], help="操作")
    verdict_parser.add_argument("chain_id", nargs="?", help="Chain ID")
    verdict_parser.add_argument("-n", "--limit", type=int, default=20, help="列表数量")
    
    # config
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("action", choices=["show", "init", "edit"], help="操作")
    
    # benchmark
    bench_parser = subparsers.add_parser("benchmark", help="运行 Benchmark")
    bench_parser.add_argument("-n", "--num", type=int, default=8, help="案例数量")
    
    args = parser.parse_args()
    
    if args.cmd == "judge":
        cmd_judge(args.task, args.verbose)
    elif args.cmd == "shell":
        cmd_shell()
    elif args.cmd == "web":
        from web_console import run
        run(args.port)
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "verdict":
        cmd_verdict(args)
    elif args.cmd == "config":
        cmd_config(args)
    
    elif args.cmd == "benchmark":
        report = run_benchmark()
        print(f"\n✅ Benchmark 完成")
    else:
        # 无参数时进入交互模式
        cmd_shell()


if __name__ == "__main__":
    main()
