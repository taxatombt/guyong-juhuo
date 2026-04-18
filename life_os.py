#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ADAPTER_OK = False
try:
    from subsystems.judgment.emotion_adapter import get_emotion_modulation
    ADAPTER_OK = True
except ImportError: pass
TASK_DEMAND = {
    "写报告": 80, "写BP": 90, "写代码": 85, "写邮件": 20,
    "做PPT": 70, "开会": 50, "见客户": 60, "健身": 30,
    "打电话": 30, "整理文件": 20, "阅读": 40, "思考": 70,
    "决策": 80, "谈判": 75, "面试": 65, "学习": 60,
}
def parse_energy(s):
    s = s.strip().rstrip("%")
    try: return max(0, min(100, int(s)))
    except: return 50
def parse_pad(s):
    if not s: return None
    try:
        p,a,d = [float(x.strip()) for x in s.split(",", 2)]
        return {"P": p, "A": a, "D": d}
    except: return None
def parse_tasks(s):
    return [
        {"name": n.strip(), "demand": TASK_DEMAND.get(n.strip(), 50),
         "priority": "high" if TASK_DEMAND.get(n.strip(), 50) >= 70
         else "medium" if TASK_DEMAND.get(n.strip(), 50) >= 40 else "low"}
        for n in s.split(",") if n.strip()
    ]
LABEL_TEXT = {
    "anxiety": "焦虑", "excitement": "兴奋", "anger": "愤怒",
    "fear": "恐惧", "joy": "愉悦", "sadness": "低落", "calm": "平静",
}
def estimate_pad(text):
    tl = text.lower()
    p = 0.5 if any(w in tl for w in ["开心","高兴","兴奋","愉快","期待"]) \
        else -0.4 if any(w in tl for w in ["焦虑","烦躁","不安","担心","累"]) else 0.0
    a = 0.4 if any(w in tl for w in ["紧张","激动","忙碌"]) \
        else -0.3 if any(w in tl for w in ["困","累"]) else 0.0
    d = 0.4 if any(w in tl for w in ["可控","能处理"]) \
        else -0.4 if any(w in tl for w in ["失控","太多"]) else 0.0
    return {"P": p, "A": a, "D": d}
def schedule_tasks(tasks, energy, em=None):
    if not tasks: return []
    label = em.emotion_label if em else "calm"
    mods = em.dim_mods if em else {}
    cog = mods.get("cognitive", 1.0)
    result = []
    for t in tasks:
        adj = int(t["demand"] * (2.0 - cog))
        if energy >= 80:
            slot = "上午优先" if t["priority"] == "high" else "下午"
            reason = "精力充沛" if adj <= 90 else "需求过高，建议拆分"
        elif energy >= 50:
            slot = "上午" if adj <= 60 else "推迟"
            reason = "精力一般" if adj <= 60 else "精力不足，建议降低难度"
        else:
            slot = "随时" if adj <= 40 else "待定"
            reason = "低能耗可完成" if adj <= 40 else "精力{}%不足".format(energy)
        item = {**t, "slot": slot, "reason": reason}
        if label == "anxiety" and t["demand"] >= 70:
            item["note"] = "[焦虑] 高认知任务，焦虑时易出错，建议拆分"
        elif label == "excitement" and t["demand"] >= 70:
            item["note"] = "[兴奋] 警惕过度乐观"
        elif label == "calm":
            item["note"] = "[平静] 适合深度分析"
        result.append(item)
    return result
def print_report(tasks, energy, em=None, pad=None):
    label = em.emotion_label if em else "未知"
    lcn = LABEL_TEXT.get(label, label)
    print("=" * 50)
    print("  Life OS - 今日计划")
    print("=" * 50)
    print("  精力: {}%".format(energy))
    if pad:
        print("  情绪: PAD={} -> {}".format(pad, lcn))
    elif em:
        print("  情绪: {}".format(lcn))
    print()
    sched = schedule_tasks(tasks, energy, em)
    for p_lbl, name in [("high","高优先级"),("medium","中优先级"),("low","低优先级")]:
        g = [t for t in sched if t["priority"] == p_lbl]
        if not g: continue
        print("  [{}] ({}项)".format(name, len(g)))
        for t in g:
            e = "!" if t["slot"] in ("待定","推迟") else ">"
            print("    {} {} ({}) - {}".format(e, t["name"], t["slot"], t["reason"]))
            if t.get("note"):
                print("      {}".format(t["note"]))
        print()
    if em:
        c = em.confidence_adjustment
        direction = "下调" if c < 0 else "上调"
        print("  [调制] 信心度: {}{:.0%}".format(direction, abs(c)))
        if em.recommended_dims:
            print("  [加强] {}".format(em.recommended_dims))
        if em.suppressed_dims:
            print("  [削弱] {}".format(em.suppressed_dims))
    print("=" * 50)
def main():
    p = argparse.ArgumentParser(description="Life OS调度器")
    p.add_argument("tasks", nargs="?", default="")
    p.add_argument("-e", "--energy", default="50")
    p.add_argument("-m", "--emotion", default="")
    p.add_argument("-i", "--interactive", action="store_true")
    args = p.parse_args()
    if args.interactive or not args.tasks:
        print("Life OS Interactive Mode")
        task_input = input("任务列表 (逗号分隔)> ").strip()
        energy_str = input("精力 (0-100, 默认50)> ").strip() or "50"
        pad_str = input("PAD (P,A,D 如 -0.6,0.4,-0.3, 空则自动估计)> ").strip()
    else:
        task_input = args.tasks
        energy_str = args.energy
        pad_str = args.emotion
    energy = parse_energy(energy_str)
    emotion_state = parse_pad(pad_str)
    if not emotion_state:
        emotion_state = estimate_pad(task_input)
        print("  自动估计PAD: {}".format(emotion_state))
    tasks = parse_tasks(task_input)
    if not tasks:
        print("Usage: python life_os.py <任务> --energy 80")
        return
    em = None
    if ADAPTER_OK:
        em = get_emotion_modulation(emotion_state)
    print_report(tasks, energy, em, emotion_state)
if __name__ == "__main__": main()
