"""
cli_status.py — Juhuo CLI status dashboard
"""
import sqlite3
import datetime
import statistics
from pathlib import Path


def run_status():
    """打印 Juhuo 状态仪表盘"""
    db = Path(__file__).parent / "data" / "juhuo.db"
    if not db.exists():
        print("❌ 数据库不存在，请先运行 `python cli.py morning`")
        return

    conn = sqlite3.connect(str(db))

    print("\n" + "=" * 52)
    print("  📊 Juhuo 状态仪表盘")
    print("=" * 52)

    # ── 1. 准确率 ─────────────────────────────────────────────────
    total = conn.execute("SELECT COUNT(*) FROM verdict_outcomes").fetchone()[0]
    correct = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=1").fetchone()[0]
    partial = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=0.5").fetchone()[0]
    wrong = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE correct=0").fetchone()[0]

    if total == 0:
        print("\n  ⚠️  暂无 verdict 数据")
        print("  运行 `python cli.py morning` 做判断后输入 verdict 积累数据")
    else:
        acc = (correct + 0.5 * partial) / total

        now = datetime.datetime.now()
        week_ago = (now - datetime.timedelta(days=7)).isoformat()
        month_ago = (now - datetime.timedelta(days=30)).isoformat()

        t7 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ?", (week_ago,)).fetchone()[0]
        c7 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ? AND correct=1", (week_ago,)).fetchone()[0]
        p7 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ? AND correct=0.5", (week_ago,)).fetchone()[0]
        acc7 = (c7 + 0.5 * p7) / t7 if t7 > 0 else None

        t30 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ?", (month_ago,)).fetchone()[0]
        c30 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ? AND correct=1", (month_ago,)).fetchone()[0]
        p30 = conn.execute("SELECT COUNT(*) FROM verdict_outcomes WHERE created_at >= ? AND correct=0.5", (month_ago,)).fetchone()[0]
        acc30 = (c30 + 0.5 * p30) / t30 if t30 > 0 else None

        trend = ""
        if acc7 is not None and acc30 is not None and acc7 > 0 and acc30 > 0:
            delta = acc7 - acc30
            trend = f"{'+' if delta > 0 else ''}{delta:.0%}"

        def bar(v, width=18):
            filled = int(v * width)
            return "█" * filled + "░" * (width - filled)

        print(f"\n  📈 预测准确率")
        print(f"  ┌{'─' * 26}┐")
        print(f"  │ 总体  {bar(acc):18s} {acc:.0%}  │")
        if acc7 is not None:
            print(f"  │ 近7天 {bar(acc7):18s} {acc7:.0%}  │")
        if acc30 is not None:
            print(f"  │ 近30天{bar(acc30):18s} {acc30:.0%}  │")
        print(f"  └{'─' * 26}┘")
        print(f"  总 verdicts: {total}  正确: {correct}  部分: {partial}  错误: {wrong}")
        if trend:
            print(f"  7天 vs 30天趋势: {trend}")

        last_row = conn.execute(
            "SELECT created_at FROM verdict_outcomes ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if last_row and t7 == 0:
            print(f"\n  ⚠️  近7天无 verdicts（最近: {last_row[0][:10]}）")
            print(f"  → `python cli.py morning` 开始今日判断")

    # ── 2. 维度准确率 ─────────────────────────────────────────────
    print(f"\n  🎯 各维度准确率")
    beliefs = conn.execute(
        "SELECT dimension, belief, hit_count, miss_count FROM dimension_beliefs WHERE user_id='default'"
    ).fetchall()
    dim_stats = []
    for b in beliefs:
        total_hm = b[2] + b[3]
        if total_hm > 0:
            dim_stats.append((b[0], b[2] / total_hm, total_hm))

    if dim_stats:
        scores = [s[1] for s in dim_stats]
        std = statistics.stdev(scores) if len(scores) >= 2 else 0.0
        for dim_id, dim_acc, n in sorted(dim_stats, key=lambda x: x[1]):
            flag = ""
            if dim_acc < 0.4:
                flag = " ⚠️ 低"
            elif dim_acc > 0.7:
                flag = " ✅ 高"
            print(f"    {dim_id:15s} {dim_acc:.0%} ({n}次){flag}")
        print(f"\n  维度标准差: {std:.3f}  {'⚠️ 不稳定' if std > 0.15 else '→ 稳定'}")
        worst = min(dim_stats, key=lambda x: x[1])
        best = max(dim_stats, key=lambda x: x[1])
        print(f"  最需关注: {worst[0]} ({worst[1]:.0%})  最好: {best[0]} ({best[1]:.0%})")
    else:
        print("  ⚪ 维度准确率未积累")

    # ── 3. Self-Evolver ───────────────────────────────────────────
    print(f"\n  🔄 Self-Evolver")
    evo_count = 0
    try:
        from subsystems.judgment.self_evolver import EvolverScheduler
        sched = EvolverScheduler.get_scheduler()
        last_run = getattr(sched, '_last_run_time', None)
        if last_run:
            print(f"  上次运行: {str(last_run)[:16]}")
    except Exception:
        pass

    try:
        evo_count = conn.execute("SELECT COUNT(*) FROM evolution_log").fetchone()[0]
        print(f"  进化次数: {evo_count}")
        if evo_count == 0:
            print("  ⚠️  从未触发（需连续3次错误）")
        else:
            last_evo = conn.execute(
                "SELECT created_at, status FROM evolution_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if last_evo:
                print(f"  最近: {last_evo[0][:10]} 状态={last_evo[1]}")
    except Exception:
        print("  ⚠️  进化日志不可用")

    # ── 4. 待处理 ─────────────────────────────────────────────────
    pending = conn.execute(
        "SELECT COUNT(*) FROM judgment_snapshots "
        "WHERE (verdict IS NULL OR verdict='' OR verdict='pending') "
        "AND task_text IS NOT NULL AND task_text != ''"
    ).fetchone()[0]
    if pending > 0:
        print(f"\n  ⏳ 待 verdict: {pending} 条 → `python cli.py verdict list`")

    conn.close()
    print("\n" + "=" * 52)
