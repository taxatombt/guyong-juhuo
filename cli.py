"""
cli.py — guyong-juhuo Agent 入口

用法:
    python cli.py                      # 交互模式
    python cli.py "任务描述"           # single judgment
    python cli.py --profile "<persona>" "任务"  # specify persona
    python cli.py pdf <file.pdf>       # 提取PDF并做十维分析
    python cli.py --list               # 列出所有 profile
    python cli.py --stats              # 查看统计
    python cli.py --lessons            # 查看教训
    python cli.py --history            # 查看历史
    python cli.py --evolution          # 生成OpenSpace进化建议
    python cli.py --create-profile "<persona>" --type rational  # 创建 profile
"""

import sys
import os
import json

pkg_dir = os.path.dirname(os.path.abspath(__file__))
parent = os.path.dirname(pkg_dir)
if parent not in sys.path:
    sys.path.insert(0, parent)


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print("guyong-juhuo Agent — 数字分身，持续自我进化")
        print()
        print("用法:")
        print("  python cli.py                      # 交互模式")
        print("  python cli.py \"任务描述\"           # 单次十维判断")
        print("  python cli.py --profile NAME \"任务\"  # 指定 persona")
        print("  python cli.py pdf <file.pdf>       # 提取PDF并做十维分析")
        print("  python cli.py web <url>            # 提取网页并做十维分析")
        print("  python cli.py --list                # 列出所有 profile")
        print("  python cli.py --stats               # 查看统计")
        print("  python cli.py --lessons             # 查看教训")
        print("  python cli.py --history             # 查看历史")
        print("  python cli.py --evolution          # 生成OpenSpace进化建议")
        print("  python cli.py --create-profile NAME --type rational  # 创建 profile")
        print("  python cli.py hub <sub>            # Hub 子系统调试")
        print()
        print("  Hub 子命令:")
        print("    hub subsystems   — 列出所有子系统")
        print("    hub check <code> — 安全检查（危险模式检测）")
        print("    hub ralph        — Ralph 循环检测状态")
        print("    hub collision   — Skill 碰撞检测")
        print("    hub evolver      — 运行 Self-Evolver 闭环")
        print("    hub evolver --summarize — 输出学习摘要")
        print("    hub sqlite       — SQLite 数据状态")
        print()
        print("Profile 类型: rational / emotional / intuitive / balanced")
        sys.exit(0)

    profile_name = None
    task = None
    cmd_mode = None  # stats/lessons/history/list/evolution/pdf/web/hub
    pdf_path = None
    create_profile = None
    create_type = "balanced"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--profile":
            profile_name = args[i + 1]
            i += 2
        elif arg == "--list":
            cmd_mode = "list"
            i += 1
        elif arg == "--stats":
            cmd_mode = "stats"
            i += 1
        elif arg == "--lessons":
            cmd_mode = "lessons"
            i += 1
        elif arg == "--history":
            cmd_mode = "history"
            i += 1
        elif arg == "--summary":
            cmd_mode = "summary"
            i += 1
        elif arg == "--evolution":
            cmd_mode = "evolution"
            i += 1
        elif arg == "pdf":
            cmd_mode = "pdf"
            pdf_path = args[i + 1]
            i += 2
        elif arg == "hub":
            cmd_mode = "hub"
            # hub 子命令在 cmd_mode 块中处理，i 指向子命令
            i += 1
        elif arg == "web":
            cmd_mode = "web"
            web_url = args[i + 1]
            i += 2
        elif arg == "--create-profile":
            create_profile = args[i + 1]
            i += 2
        elif arg == "--type":
            create_type = args[i + 1]
            i += 2
        elif not arg.startswith("--"):
            # 尝试 hub 子命令（hub subsystems / hub check 等）
            if arg == "hub" and i + 1 < len(args):
                cmd_mode = "hub"
                i += 1  # 跳过 "hub"，保留子命令在 args[i]
            else:
                task = " ".join(args[i:])
            break
        else:
            i += 1

    # 命令模式
    if cmd_mode:
        # Hub 命令先行（避免 judgment.profile 等无效 import）
        if cmd_mode == "hub":
            import hub as _hub
            _h = _hub.get_hub()
            sub = args[i] if i < len(args) else "subsystems"
            if sub == "check":
                code = " ".join(args[i+1:]) if i+1 < len(args) else ""
                if not code:
                    print("用法: hub check <代码>")
                    return
                findings = _h.security.check(code)
                print(_h.security.format_findings(findings))
            elif sub == "collision":
                print("[!] 请直接用 Python 调用:")
                print("    detector = hub.get_hub().collision.create()")
                print("    hub.get_hub().collision.detect(detector, {'tdd': ['test'], 'unit-test': ['test']})")
            elif sub == "ralph":
                from curiosity.ralph_loop import RalphLoop, RalphState
                print("RalphLoop 子系统:")
                print(f"  RalphState 是 @dataclass，包含字段:")
                print(f"    iteration, has_new_info, promise_met, deadlock, message")
                print()
                print("  使用示例:")
                print("    loop = hub.get_hub().ralph.create(promise=lambda: len(items) >= 5)")
                print("    result = loop.run()")
            elif sub == "evolver":
                evo = _h.evolver
                # 检查 --summarize flag
                if i + 1 < len(args) and args[i + 1] == "--summarize":
                    print(evo.summarize())
                else:
                    result = evo.run_cycle()
                    print(f"[OK] Self-Evolver 闭环完成")
                    print(f"  记录处理: {result.records_processed}")
                    print(f"  新模式: {result.new_patterns}")
                    print(f"  Lessons 新增: {result.lessons_added}")
            elif sub == "sqlite":
                print(_h.sqlite.summary())
            elif sub == "subsystems":
                print("=== Hub 子系统列表 ===")
                subs = [
                    ("judgment",     "十维判断引擎"),
                    ("curiosity",    "好奇心引擎"),
                    ("causal",       "因果记忆"),
                    ("output",       "格式化输出"),
                    ("emotion",      "情绪系统"),
                    ("feedback",     "反馈记录"),
                    ("action_signal","行动信号"),
                    ("ralph",        "Ralph 循环检测"),
                    ("collision",    "Skill 碰撞检测"),
                    ("security",     "安全检查"),
                    ("benchmark",    "GDPVal 基准测试"),
                    ("observe",      "被动工具捕获"),
                    ("diff_tracker", "决策影响追踪"),
                    ("evolver",      "Self-Evolver 闭环"),
                ]
                for name, desc in subs:
                    print(f"  hub.{name:15s} — {desc}")
            else:
                print(f"未知 hub 子命令: {sub}")
                print("用法: hub subsystems|check|ralph|collision|evolver")
            return

        # judgment 模块不存在，尝试兼容导入
        try:
            from judgment.profile import list_profiles
            from judgment.memory import get_stats, get_lessons, get_decisions, summary as memory_summary
            _jm_available = True
        except ImportError:
            _jm_available = False

        if cmd_mode == "list":
            if not _jm_available:
                print("[!] judgment.profile 模块不可用，跳过")
                return
            profiles = list_profiles()
            print("Profiles:", ", ".join(profiles) if profiles else "(空)")
            return
        elif cmd_mode == "stats":
            if not _jm_available:
                print("[!] judgment.memory 模块不可用，跳过")
                return
            stats = get_stats()
            print(f"总判断数: {stats['total']}")
            print(f"正确判断: {stats['good']}")
            print(f"准确率: {stats['accuracy']:.1f}%")
            return
        elif cmd_mode == "lessons":
            if not _jm_available:
                print("[!] judgment.memory 模块不可用，跳过")
                return
            lessons = get_lessons()
            if not lessons:
                print("暂无教训")
            for l in lessons[:10]:
                print(f"  [{l['count']}次] {l['dimension']}: {l['pattern']}")
            return
        elif cmd_mode == "history":
            if not _jm_available:
                print("[!] judgment.memory 模块不可用，跳过")
                return
            decisions = get_decisions(10)
            for d in decisions:
                fb = d.get("feedback", "")
                print(f"  [{d['timestamp'][:10]}] {d['task'][:40]}: {d['decision'][:25]} [{fb}]")
            return
        elif cmd_mode == "summary":
            if not _jm_available:
                print("[!] judgment.memory 模块不可用，跳过")
                return
            s = memory_summary()
            print(f"总判断数: {s['total_decisions']}")
            print(f"准确率: {s['stats']['accuracy']:.1f}%")
            print(f"教训数: {len(s['top_lessons'])}")
            return
        elif cmd_mode == "evolution":
            # OpenSpace 进化建议
            from execution_analyzer import ExecutionAnalyzer
            analyzer = ExecutionAnalyzer()
            suggestions = analyzer.generate_evolution_suggestions()
            print("=== OpenSpace 进化建议 ===")
            print()
            if not suggestions:
                print("没有需要进化的技能")
            else:
                for s in suggestions:
                    print(f"[{s['suggestion']}] skill={s['skill_id']} 成功率={s['success_rate']:.1%}")
                    print(f"  原因: {s['reason']}")
                    print()
            return
        elif cmd_mode == "pdf":
            # PDF提取 + 十维分析
            from perception import extract_pdf_to_judgment_input
            from judgment.router import check10d, format_report

            print(f"提取PDF: {pdf_path}")
            print("正在提取并过滤...")
            content = extract_pdf_to_judgment_input(pdf_path)
            print()
            print("=== 过滤后内容（前800字符）===")
            if len(content) > 800:
                print(content[:800] + "...\n(内容被截断，完整内容用于分析)")
            else:
                print(content)
            print()
            print("=== 十维分析结果 ===")
            result = check10d(content, profile_name=profile_name)
            print(format_report(result))
            return
        elif cmd_mode == "web":
            # 网页提取 + 十维分析
            from perception import extract_web_to_judgment_input
            from judgment.router import check10d, format_report

            print(f"提取网页: {web_url}")
            print("正在提取并过滤...")
            content = extract_web_to_judgment_input(web_url)
            print()
            print("=== 过滤后内容（前800字符）===")
            if len(content) > 800:
                print(content[:800] + "...\n(内容被截断，完整内容用于分析)")
            else:
                print(content)
            print()
            print("=== 十维分析结果 ===")
            result = check10d(content, profile_name=profile_name)
            print(format_report(result))
            return
        elif cmd_mode == "hub":
            # Hub 统一入口 — 各子系统调试
            import hub as _hub
            _h = _hub.get_hub()

            sub = args[i] if i < len(args) else "subsystems"
            if sub == "check":
                code = " ".join(args[i+1:]) if i+1 < len(args) else ""
                if not code:
                    print("用法: hub check <代码>")
                    return
                findings = _h.security.check(code)
                print(_h.security.format_findings(findings))
            elif sub == "collision":
                print("[!] 请提供 skills dict，或用 python -c 直接调用")
                print("    detector = hub.get_hub().collision.create()")
                print("    hub.get_hub().collision.detect(detector, {'tdd': ['test'], 'unit-test': ['test']})")
            elif sub == "ralph":
                from curiosity.ralph_loop import RalphLoop, RalphState
                print("RalphLoop 子系统:")
                print(f"  RalphState 是 @dataclass，包含字段:")
                print(f"    iteration, has_new_info, promise_met, deadlock, message")
                print()
                print("  使用示例:")
                print("    loop = hub.get_hub().ralph.create(promise=lambda: len(items) >= 5)")
                print("    result = loop.run()")
            elif sub == "evolver":
                evo = _h.evolver
                # 检查 --summarize flag
                if i + 1 < len(args) and args[i + 1] == "--summarize":
                    print(evo.summarize())
                else:
                    result = evo.run_cycle()
                    print(f"[OK] Self-Evolver 闭环完成")
                    print(f"  记录处理: {result.records_processed}")
                    print(f"  新模式: {result.new_patterns}")
                    print(f"  Lessons 新增: {result.lessons_added}")
            elif sub == "sqlite":
                print(_h.sqlite.summary())
            elif sub == "subsystems":
                print("=== Hub 子系统列表 ===")
                subs = [
                    ("judgment",     "十维判断引擎"),
                    ("curiosity",    "好奇心引擎"),
                    ("causal",       "因果记忆"),
                    ("output",       "格式化输出"),
                    ("emotion",      "情绪系统"),
                    ("feedback",     "反馈记录"),
                    ("action_signal","行动信号"),
                    ("ralph",        "Ralph 循环检测"),
                    ("collision",    "Skill 碰撞检测"),
                    ("security",     "安全检查"),
                    ("benchmark",    "GDPVal 基准测试"),
                    ("observe",      "被动工具捕获"),
                    ("diff_tracker", "决策影响追踪"),
                    ("evolver",      "Self-Evolver 闭环"),
                ]
                for name, desc in subs:
                    print(f"  hub.{name:15s} — {desc}")
            elif sub == "observe":
                hook = _h.observe.create()
                print(f"ObserveHook 创建成功: {hook}")
                print("  工具调用将被动记录到 data/memory/fast/")
            else:
                print(f"未知 hub 子命令: {sub}")
                print("用法: hub check|collision|ralph|subsystems")
            return

    # 创建 profile
    if create_profile:
        from judgment.profile import create_persona
        p = create_persona(create_profile, create_type)
        print(f"已创建 profile: {p['name']} ({p['style']})")
        print(f"  价值观: {', '.join(p['values'])}")
        print(f"  已知偏差: {', '.join(p['biases'])}")
        return

    # 初始化 agent
    from judgment.agent import JudgmentAgent
    agent = JudgmentAgent(profile_name=profile_name)

    # 运行
    if task:
        agent.run(task=task)
    else:
        agent.run(interactive=True)


if __name__ == "__main__":
    main()
