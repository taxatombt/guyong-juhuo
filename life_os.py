#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADAPTER_OK = False
try:
    from subsystems.judgment.emotion_adapter import get_emotion_modulation
    ADAPTER_OK = True
except ImportError:
    pass

TASK_DEMAND = {
    "report": 80, "bp": 90, "coding": 85, "email": 20, "ppt": 70,
    "meeting": 50, "client": 60, "gym": 30, "call": 30,
    "file": 20, "read": 40, "think": 70, "decision": 80,
    "negotiate": 75, "interview": 65, "learn": 60,
}

def parse_energy(s):
    s = s.strip().rstrip('%')
    return max(0, min(100, int(s))) if s.isdigit() else 50

def parse_pad(s):
    if not s: return None
    if ',' in s and s.count(',') == 2:
        try:
            parts = s.split(',')
            return dict(zip(['P','A','D'], [float(x) for x in parts]))
        except:
            return None
    return None

def parse_tasks(s):
    sep = "," if "," in s else (";" if ";" in s else None)
    raw = s.split(sep) if sep else [s]
    tasks = []
    for t in raw:
        t = t.strip()
        if not t: continue
        m = re.search(r'@(\d+)', t)
        hint = int(m.group(1)) if m else None
        t = re.sub(r'@\d+', '', t).strip()
        tasks.append({'name': t, 'demand': hint})
    return tasks

def infer_demand(name):
    for kw, d in TASK_DEMAND.items():
        if kw in name.lower(): return d
    return 50

def build_plan(tasks, energy, mod, label):
    plan = []
    remaining = energy
    hour = 9
    rec = mod.get('recommended_dims', []) if mod else []
    for t in tasks:
        demand = t['demand'] if t['demand'] is not None else infer_demand(t['name'])
        tag = ''
        if 'cognitive' in rec: tag = ' [clarity]'
        elif label == 'anxiety' and demand > 60: tag = ' [defer]'
        elif label == 'excitement' and demand > 70: tag = ' [now_best]'
        block_h = max(0.5, demand / 40.0)
        if remaining >= demand / 2.0:
            end_h = hour + int(block_h)
            end_m = int((block_h - int(block_h)) * 60)
            plan.append(f'{hour:02d}:00-{end_h:02d}:{end_m:02d}  {t["name"]}{tag}  @{demand}')
            remaining -= demand
            hour = end_h
            if hour >= 12:
                plan.append(f'{hour:02d}:00-{hour+1:02d}:00  [lunch_break]  @0')
                hour += 1
                remaining = min(100, remaining + 30)
        else:
            plan.append(f'[tomorrow]  {t["name"]}  @{demand}  (energy={remaining}% insufficient)')
    return plan

def main():
    p = argparse.ArgumentParser(description='Life OS minimum CLI')
    p.add_argument('tasks', nargs='?', default='')
    p.add_argument('-e', '--energy', default='70')
    p.add_argument('-m', '--emotion', default='')
    p.add_argument('-i', '--interactive', action='store_true')
    args = p.parse_args()
    tasks_raw = args.tasks
    energy = parse_energy(args.energy)
    pad = parse_pad(args.emotion)
    if args.interactive:
        tasks_raw = input('Tasks: ').strip() or tasks_raw
        e = input('Energy (0-100): ').strip()
        if e: energy = parse_energy(e)
        p_in = input('PAD (P,A,D): ').strip()
        if p_in: pad = parse_pad(p_in)
    tasks = parse_tasks(tasks_raw) if tasks_raw else []
    if not tasks:
        print('Usage: python life_os.py "write_bp,email,gym" -e 45 -m -0.6,0.4,-0.3')
        return
    print()
    print('=' * 50)
    print('Life OS Daily Plan')
    print('=' * 50)
    print(f'Energy: {energy}%')
    print(f'Tasks: {len(tasks)} items')
    if pad:
        print(f'PAD: P={pad["P"]:+.1f} A={pad["A"]:+.1f} D={pad["D"]:+.1f}')
    else:
        print('PAD: neutral')
    print()
    mod, label, conf_adj = None, 'calm', 0.0
    if pad and ADAPTER_OK:
        mod = get_emotion_modulation(pad)
        label = mod.emotion_label
        conf_adj = mod.confidence_adjustment
        print(f'Emotion: {mod.emotion_label} (intensity={mod.intensity})')
        if mod.recommended_dims: print(f'  Boost: {mod.recommended_dims}')
        if mod.suppressed_dims: print(f'  Reduce: {mod.suppressed_dims}')
        print(f'  Confidence adj: {mod.confidence_adjustment:+.2f}')
        print()
        mod_dict = mod.__dict__
    else:
        mod_dict = None
    plan = build_plan(tasks, energy, mod_dict, label)
    print('--- Plan ---')
    for item in plan: print(f'  {item}')
    print()
    if conf_adj != 0:
        print(f'[Emotion] Confidence adjusted by {conf_adj:+.2f}')
    print()
    if not pad and ADAPTER_OK:
        print('Tip: -m -0.6,0.4,-0.3 = anxiety  |  -m 0.8,0.6,0.5 = excitement')

if __name__ == '__main__':
    main()
