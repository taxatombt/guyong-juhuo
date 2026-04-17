#!/usr/bin/env python3
# judgment/closed_loop.py

import sqlite3,json,time,hashlib,os,threading,logging
from threading import Lock
from typing import Optional,Dict,List,Any

_DB=os.path.join(os.path.dirname(__file__),"..","data","evolutions","juhuo.db")
_DIR=os.path.dirname(_DB)
_OUT=os.path.join(os.path.dirname(__file__),"..","data","outcomes.jsonl")
MAX=100;DECAY=0.1;MAXD=0.15;SH=0.95;SL=0.05
DIMS=["cognitive","game_theory","economic","dialectical","emotional","intuitive","moral","social","temporal","metacognitive"]
_lock=Lock();_lt=None;_lstop=threading.Event()
_log=logging.getLogger("cl")

def _g():
    os.makedirs(_DIR,exist_ok=True)
    c=sqlite3.connect(_DB,timeout=10)
    c.execute("PRAGMA journal_mode=WAL");return c
def _h(t):return hashlib.sha256(t.encode()).hexdigest()[:16]
def _n():return time.time()

def init():
    c=_g()
    try:
        c.execute("CREATE TABLE IF NOT EXISTS causal_chain (id INTEGER PRIMARY KEY,chain_id TEXT,ts REAL,task_hash TEXT,task_text TEXT,dimensions TEXT,outcome REAL,corrected INTEGER DEFAULT 0,notes TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS dimension_beliefs (dim_id TEXT PRIMARY KEY,belief REAL DEFAULT 0.5,hit_count INTEGER DEFAULT 0,miss_count INTEGER DEFAULT 0,last_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS judgment_snapshots (id INTEGER PRIMARY KEY,chain_id TEXT UNIQUE,ts REAL,task_hash TEXT,task_text TEXT,dimensions TEXT,weights TEXT,answers TEXT,confidence TEXT,complexity TEXT,emotion_label TEXT,causal_has_history INTEGER DEFAULT 0,outcome_auto REAL,corrected INTEGER DEFAULT 0)")
        for d in DIMS:c.execute("INSERT OR IGNORE INTO dimension_beliefs (dim_id,belief) VALUES (?,0.5)",(d,))
        c.commit()
    finally:c.close()

def snapshot_judgment(chain_id,task_text,dimensions,weights,result,complexity):
    """Frozen Snapshot: judgment调用时立即落盘，同时记录causal_chain"""  
    task_hash=_h(task_text);now=_n()
    answers=result.get("answers",{});emotion=result.get("emotion",{});curiosity=result.get("curiosity",{})
    dim_conf=result.get("dim_confidence",{});confidence={d:dim_conf.get(d,0.5) for d in dimensions}
    emotion_label=(emotion.get("detected_emotions",[""])[0] or "") if isinstance(emotion,dict) else ""
    causal_hist=1 if curiosity.get("has_gap") else 0
    c=_g()
    try:
        c.execute("INSERT OR REPLACE INTO judgment_snapshots (chain_id,ts,task_hash,task_text,dimensions,weights,answers,confidence,complexity,emotion_label,causal_has_history) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (chain_id,now,task_hash,task_text[:500] or "",json.dumps(dimensions,ensure_ascii=False),json.dumps(weights,ensure_ascii=False),json.dumps(answers,ensure_ascii=False),json.dumps(confidence,ensure_ascii=False),complexity,emotion_label,causal_hist))
        c.execute("INSERT INTO causal_chain (chain_id,ts,task_hash,task_text,dimensions,outcome) VALUES (?,?,?,?,?,NULL)",
            (chain_id,now,task_hash,task_text[:300] or "",json.dumps({"dims":dimensions,"weights":weights},ensure_ascii=False)))
        c.execute("DELETE FROM causal_chain WHERE id NOT IN (SELECT id FROM causal_chain ORDER BY ts DESC LIMIT ?)",(MAX,))
        c.commit()
        _log.debug(f"[snapshot] {chain_id} dims={len(dimensions)}")
        return True
    except Exception as e:
        _log.warning(f"[snapshot] failed: {e}");return False
    finally:c.close()

def receive_verdict(chain_id=None,task_text=None,correct=True,notes=""):
    """接收事后验证，更新维度信念，触发三个闭环hook"""  
    c=_g()
    try:
        target=None
        if chain_id:
            r=c.execute("SELECT id,dimensions FROM causal_chain WHERE chain_id=? AND corrected=0",(chain_id,)).fetchone()
            if r: target=r
        elif task_text:
            r=c.execute("SELECT id,dimensions FROM causal_chain WHERE task_hash=? AND corrected=0 ORDER BY ts DESC LIMIT 1",(_h(task_text),)).fetchone()
            if r: target=r
        if not target: return {"updated":False,"reason":"no_record_found"}
        rec_id,dims_json=target;dims_data=json.loads(dims_json);correction=1.0 if correct else -1.0;changes={}
        for dim_id in dims_data.get("dims",[]):
            row=c.execute("SELECT belief,hit_count,miss_count FROM dimension_beliefs WHERE dim_id=?",(dim_id,)).fetchone()
            if not row: continue
            b,h,m=row;delta=max(-MAXD,min(MAXD,DECAY*correction));nb=max(SL,min(SH,b+delta))
            c.execute("UPDATE dimension_beliefs SET belief=?,hit_count=?,miss_count=?,last_id=? WHERE dim_id=?",(nb,h+(1 if correct else 0),m+(0 if correct else 1),chain_id,dim_id))
            changes[dim_id]={"belief_before":round(b,4),"belief_after":round(nb,4),"delta":round(delta,4)}
        c.execute("UPDATE causal_chain SET corrected=1,outcome=?,notes=? WHERE id=?",(1.0 if correct else 0.0,notes[:200],rec_id))
        c.execute("UPDATE judgment_snapshots SET outcome_auto=?,corrected=1 WHERE chain_id=?",(1.0 if correct else 0.0,chain_id))
        c.commit()
        _trigger_fitness(chain_id,task_text,correct,changes)
        _trigger_curiosity(chain_id,task_text,correct,changes)
        
        # 【闭环Step3】Self-Evolver 验证闭环 — 记录每次判决结果
        try:
            from judgment.self_evolover import EvolverScheduler
            _sch = EvolverScheduler()
            _sch.record_outcome(1 if correct else 0)
            _log.debug(f"[self_evolver] recorded outcome: correct={correct}")
        except Exception as e:
            _log.debug(f"[self_evolver] record_outcome skip: {e}")
        # 【闭环Step1】judgment → causal_memory
        _trigger_causal_memory(chain_id,task_text,dims_data.get("dims",[]),dims_data.get("weights",{}),correct,notes,1.0 if correct else 0.0)
        
        # Stop Hook: 捕获verdict行为
        try:
            from judgment.stop_hook import capture_verdict
            capture_verdict(chain_id, correct, notes)
        except Exception:
            pass
        
        _log.info(f"[verdict] chain={chain_id} correct={correct} dims={list(changes.keys())}")
        return {"updated":True,"chain_id":chain_id,"changes":changes}
    finally:c.close()

def _trigger_fitness(chain_id,task_text,correct,changes):
    try:
        from judgment.fitness_baseline import FitnessBaseline
        FitnessBaseline().record(chain_id,task_text,correct,changes)
    except Exception as e:_log.debug(f"fitness trigger skip: {e}")
    # P1改进: fitness_evolution反馈循环
    try:
        from judgment.fitness_evolution import record_judgment_outcome
        dims = list(changes.keys()) if changes else []
        weights = {dim: changes[dim].get("belief_after", 0.5) for dim in dims} if changes else {}
        if dims:
            record_judgment_outcome(
                chain_id=chain_id,
                task_text=task_text or "",
                dimensions=dims,
                weights=weights,
                correct=correct,
            )
    except Exception as e2:_log.debug(f"fitness_evolution trigger skip: {e2}")

def _trigger_curiosity(chain_id,task_text,correct,changes):
    try:
        from emotion_system.emotion_system import EmotionSystem
        es=EmotionSystem();es.detect_emotion(task_text,{"task":task_text,"dim_confidence":{},"meta":{}});pad=es.get_pad_state()
        from curiosity.curiosity_engine import trigger_from_verdict
        trigger_from_verdict(chain_id,task_text,correct,pad,changes)
    except Exception as e:_log.debug(f"curiosity trigger skip: {e}")

def _trigger_causal_memory(chain_id, task_text, dimensions, weights, correct, notes, outcome_value):
    """
    【闭环Step1】judgment → causal_memory
    把判定结果写入因果事件图，形成 judgment→outcome 闭环。

    Args:
        chain_id: 判定链ID
        task_text: 任务描述
        dimensions: 维度列表
        weights: 维度权重
        correct: 是否正确
        notes: 备注
        outcome_value: 原始 outcome 值 (1.0/0.0)
    """
    try:
        from causal_memory.causal_memory import record_event, check_and_trigger_self_model_update
        event_type = "judgment_verdict"
        description = f"判断{'正确' if correct else '错误'}：{task_text[:80]}"
        outcome_label = "correct" if correct else "incorrect"
        judgment_summary = {
            "dims": dimensions,
            "weights": weights,
            "correct": correct,
            "outcome_value": outcome_value,
        }
        tags = ["judgment", "verdict", outcome_label] + [d for d in dimensions if d]

        event_id = record_event(
            event_type=event_type,
            description=description,
            what_happened=f"判断{'正确' if correct else '错误'}于 {task_text[:100]}",
            why_i_think_so=f"维度={dimensions}, 权重={weights}",
            outcome=outcome_label,
            judgment_summary=judgment_summary,
            tags=tags,
            chain_id=chain_id,
        )

        # 【闭环Step2】causal_memory 内部检测 pattern 阈值 → 触发 self_model 更新
        check_and_trigger_self_model_update(
            task=task_text,
            dimensions=dimensions,
            correct=correct,
            pattern_key=f"chain:{chain_id}",
        )

        _log.debug(f"[causal_memory] recorded verdict event_id={event_id}")
        return event_id
    except Exception as e:
        _log.debug(f"[causal_memory] trigger skip: {e}")
        return None

def get_prior_adjustments()->Dict[str,float]:
    c=_g()
    try:return {r[0]:r[1] for r in c.execute("SELECT dim_id,belief FROM dimension_beliefs")}
    finally:c.close()

def get_recent_chains(limit=10):
    c=_g()
    try:return [{"chain_id":r[0],"ts":r[1],"task_text":r[2],"outcome":r[3],"corrected":bool(r[4])} for r in c.execute("SELECT chain_id,ts,task_text,outcome,corrected FROM causal_chain ORDER BY ts DESC LIMIT ?",(limit,)).fetchall()]
    finally:c.close()

def get_dimension_beliefs()->Dict[str,Dict[str,Any]]:
    c=_g()
    try:return {r[0]:{"belief":r[1],"hit":r[2],"miss":r[3]} for r in c.execute("SELECT dim_id,belief,hit_count,miss_count FROM dimension_beliefs")}
    finally:c.close()

# ── 后台 verdict 监听器（Auto闭环核心）───────────────────────────────
# 监听 data/outcomes.jsonl，新outcome写入时自动触发 receive_verdict
# 轮询间隔：2秒，连续3次空读后退出（节省资源）

def _verdict_signal_listener():
    """后台线程：监听 outcomes.jsonl，自动调用 receive_verdict"""  
    empty_count=0
    while not _lstop.is_set():
        _lstop.wait(timeout=2)
        if _lstop.is_set(): break
        try:
            if not os.path.exists(_OUT): empty_count+=1; continue
            with open(_OUT,encoding="utf-8") as f:
                lines=[l for l in f if l.strip()]
            if not lines:
                empty_count+=1
                if empty_count>=3: break
                continue
            empty_count=0
            last=json.loads(lines[-1])
            # 格式：{task_text, outcome (True/False/1.0/0.0), verdict_recorded, chain_id?}
            if last.get("verdict_recorded"): continue
            outcome_val=last.get("outcome",True)
            correct=bool(outcome_val) if isinstance(outcome_val,bool) else (float(outcome_val)>0.5)
            task_text=last.get("task_text","")
            chain_id=last.get("chain_id")
            result=receive_verdict(chain_id=chain_id,task_text=task_text if not chain_id else None,correct=correct,notes="auto_from_outcome_tracker")
            if result.get("updated"):
                last["verdict_recorded"]=True
                lines[-1]=json.dumps(last,ensure_ascii=False)+"\n"
                with open(_OUT,"w",encoding="utf-8") as f2:
                    f2.writelines(lines)
                _log.info(f"[listener] verdict recorded for chain={chain_id}")
        except Exception as e:
            _log.debug(f"[listener] poll error: {e}")
    _log.info("[listener] stopped")

def start_verdict_listener():
    """启动后台 verdict 监听线程（幂等）"""  
    global _lt
    if _lt and _lt.is_alive(): return
    _lstop.clear()
    _lt=threading.Thread(target=_verdict_signal_listener,daemon=True,name="verdict_listener")
    _lt.start()
    _log.info("[listener] started")

def stop_verdict_listener():
    """停止监听线程"""  
    _lstop.set()
    if _lt: _lt.join(timeout=3)
    _log.info("[listener] stop requested")

def is_listener_active()->bool:
    return _lt is not None and _lt.is_alive()

# ── record_judgment wrapper（兼容 router.py 的调用方式）───────────────
# 旧接口: record_judgment(task_text, dimensions, weights, reasoning, outcome)
# 新实现: 内部调用 snapshot_judgment，同时写入 causal_chain + judgment_snapshots
def record_judgment(task_text, dimensions, weights, reasoning=None, outcome=None):
    chain_id = f"j_{int(time.time()*1000)}"
    dummy_result = {"answers": {}, "meta": {"reasoning": reasoning or {}}, "emotion": {}, "curiosity": {}, "dim_confidence": {}}
    snapshot_judgment(chain_id, task_text, dimensions, weights, dummy_result, "auto")
    return chain_id

# 兼容别名
record_judgment = record_judgment  # 已经是新函数
