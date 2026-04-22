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
from judgment.biography import log, format_profile, get_all

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
        pred_act = result.get('predicted_action', '')
        pred_conf = result.get('prediction_confidence', 0)
        if pred_act and pred_act not in ('未知', '未知'):
            src = result.get('prediction_source', '')
            src_map = {'verdict_extraction':'绵弁解析','llm':'LLM预测','llm_raw':'LLM原始','none':'无'}
            src_ch = src_map.get(src, src)
            print(f"  → 预测你会选择: 【{pred_act}】 (置信度 {pred_conf*100:.0f}%, 来源: {src_ch})")
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



def cmd_actual(args):
    """Record actual choice and compute outcome_score"""
    chain_id = getattr(args, 'chain_id', None)
    actual = getattr(args, 'actual', None)
    if not chain_id or not actual:
        print("Usage: verdict --actual -c <chain_id> -a \"actual choice\"")
        return
    try:
        from judgment.verdict_collector import receive_actual_choice
        result = receive_actual_choice(chain_id, actual)
        if result.get("ok"):
            pred = result.get("predicted_action", "")
            score = result.get("outcome_score", 0)
            hit = result.get("hit", False)
            hit_str = "\u2713 \u547d\u4e2d" if hit else "\u2717 \u672a\u547d\u4e2d"
            print(f"\u673a\u5236\u9884\u6d4b: {pred}")
            print(f"\u7528\u6237\u5b9e\u9645: {actual}")
            print(f"\u547d\u4e2d\u72b6\u6001: {hit_str}")
            print(f"outcome_score: {score:.2f}")
        else:
            print(f"\u9519\u8bef: {result.get('error', 'unknown')}")
    except Exception as e:
        print(f"ERROR: {e}")

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

    elif args.action == "actual":
        chain_id = args.chain_id_arg or args.chain_id
        actual = args.actual_arg
        if not chain_id or not actual:
            print("Usage: verdict actual -c <chain_id> -a \"用户实际\u9009\u62e9\"")
            return
        try:
            from judgment.verdict_collector import receive_actual_choice
            result = receive_actual_choice(chain_id, actual)
            if result.get("ok"):
                pred = result.get("predicted_action", "")
                score = result.get("outcome_score", 0)
                hit = result.get("hit", False)
                hit_str = "✓ 命中" if hit else "✗ 未命中"
                print(f"机制预测: {pred}")
                print(f"用户实际: {actual}")
                print(f"命中状态: {hit_str}")
                print(f"outcome_score: {score:.2f}")
            else:
                print(f"Error: {result.get('error', 'unknown')}")
        except Exception as e:
            print(f"ERROR: {e}")


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


def cmd_bio(args):
    """生平事实管理"""
    if args.action == "show":
        print(format_profile())
    
    elif args.action == "add":
        if not args.fact:
            print("用法: juhuo bio add \"我30岁程序员\"")
            return
        # 自动抽取
        from judgment.biography import extract_from_text, log_batch
        facts = extract_from_text(args.fact)
        if not facts:
            print("未识别到生平信息，请手动指定类别：juhuo bio add \"...\" -c 职业")
            return
        added = log_batch(facts, source="user")
        print(f"[OK] 已添加 {added} 条生平信息：")
        for f in facts:
            print(f"   [{f['category']}] {f['fact']}")
    
    elif args.action == "list":
        facts = get_all()
        if not facts:
            print("(暂无生平信息)")
            return
        from judgment.biography import _CAT_DISPLAY
        for f in facts:
            cat = _CAT_DISPLAY.get(f["category"], f["category"])
            print(f"  [{cat}] {f['fact']} (命中:{f['mentions']})")


def cmd_behavior(args):
    """途径3：juhuo agent 行为日志"""
    from judgment.behavior_logger import (
        get_behavior_stats, get_recent_behaviors, get_behavior,
        ActionChannel,
    )
    if args.action == "stats":
        stats = get_behavior_stats()
        print("\n[*] Agent 行为统计")
        print(f"  总行为数：{stats['total_behaviors']}")
        for ch, info in stats["channel_breakdown"].items():
            avg = info["avg_outcome"]
            avg_str = f"{avg:.2f}" if avg is not None else "未验证"
            print(f"  [{ch}] {info['count']}次 | avg_outcome={avg_str} | verified={info['verified']}")

    elif args.action == "list":
        ch = ActionChannel(args.channel) if args.channel else None
        behaviors = get_recent_behaviors(channel=ch, limit=args.limit)
        if not behaviors:
            print("(暂无行为记录，先做判断：juhuo judge \"要不要 all in 炒股？\")")
            return
        print(f"\n[*] Agent 行为记录（共 {len(behaviors)} 条）：")
        for b in behaviors:
            v = (b.get("conclusion") or "(无)")[:35]
            tc = b.get("tool_calls", "[]")
            tc_cnt = len(eval(tc)) if isinstance(tc, str) else 0
            score = b.get("outcome_score")
            print(f"  [{b['action_channel']}] verdict={v} | tools={tc_cnt} | outcome={score}")

    elif args.action == "show":
        if not args.behavior_id:
            print("用法: juhuo behavior show <behavior_id>")
            return
        b = get_behavior(args.behavior_id)
        if not b:
            print(f"未找到：{args.behavior_id}")
            return
        print(f"\n[*] 行为 [{b['behavior_id']}]")
        print(f"  通道={b['action_channel']} | outcome={b.get('outcome_score','未验证')}")
        print(f"  结论：{b.get('conclusion','')}")
        if b.get('tool_calls'):
            import json
            try:
                tcs = json.loads(b['tool_calls'])
                for tc in tcs:
                    print(f"  - {tc['tool_name']} ({tc['duration_ms']:.0f}ms) [{tc['status']}]")
                    print(f"    → {tc.get('result_summary','')[:100]}")
            except Exception:
                pass
        if b.get('perception_summary'):
            print(f"  感知：{b['perception_summary'][:200]}")


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
    verdict_parser.add_argument("action", choices=["list", "correct", "wrong", "detail", "actual"], help="操作")
    verdict_parser.add_argument("chain_id", nargs="?", help="Chain ID")
    verdict_parser.add_argument("-c", "--chain_id_arg", dest="chain_id_arg", help="Chain ID (actual command)")
    verdict_parser.add_argument("-a", "--actual", dest="actual_arg", help="Actual user choice (actual command)")
    verdict_parser.add_argument("-n", "--limit", type=int, default=20, help="列表数量")

    # bio
    bio_parser = subparsers.add_parser("bio", help="生平事实管理")
    bio_parser.add_argument("action", choices=["show", "add", "list"], help="操作")
    bio_parser.add_argument("fact", nargs="?", help="事实文本（如：我30岁程序员）")
    
    # config
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("action", choices=["show", "init", "edit"], help="操作")
    
    # benchmark
    bench_parser = subparsers.add_parser("benchmark", help="运行 Benchmark")
    bench_parser.add_argument("-n", "--num", type=int, default=8, help="案例数量")

    # behavior（途径3：agent 行为日志）
    beh_parser = subparsers.add_parser("behavior", help="Agent 行为日志")
    beh_parser.add_argument("action", choices=["list", "stats", "show"], help="操作")
    beh_parser.add_argument("-c", "--channel", help="过滤通道（如：judgment/web_search）")
    beh_parser.add_argument("-n", "--limit", type=int, default=10, help="列表数量")
    beh_parser.add_argument("behavior_id", nargs="?", help="行为ID（show时用）")

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
        if args.action == "actual":
            args.chain_id = args.chain_id_arg or getattr(args, 'chain_id', None)
            args.actual = args.actual_arg or None
        cmd_verdict(args)
    elif args.cmd == "bio":
        cmd_bio(args)
    elif args.cmd == "config":
        cmd_config(args)
    
    elif args.cmd == "benchmark":
        report = run_benchmark()
        print(f"\n✅ Benchmark 完成")
    elif args.cmd == "behavior":
        cmd_behavior(args)
    else:
        # 无参数时进入交互模式
        cmd_shell()


if __name__ == "__main__":
    main()
