#!/usr/bin/env python3
# judgment/closed_loop.py

import sqlite3,json,time,hashlib,os,threading,logging
from threading import Lock
from typing import Optional,Dict,List,Any

_DB_PATH=os.path.join(os.path.dirname(__file__),"..","data","evolutions","juhuo.db")
_DATA_DIR=os.path.dirname(_DB_PATH)
_OUTCOMES_FILECOMES_FILE=os.path.join(os.path.dirname(__file__),"..","data","outcomes.jsonl")
MAX_CHAIN_RECORDS=100;BELIEF_DECAY=0.1;MAX_DELTA=0.15;SAT_HIGH=0.95;SAT_LOW=0.05
DIMS=["cognitive","game_theory","economic","dialectical","emotional","intuitive","moral","social","temporal","metacognitive"]
_state_lock=Lock();_listener_thread=None;_listener_stop=threading.Event()
_logger=logging.getLogger("cl")

def _get_db_conn():
    os.makedirs(_DATA_DIR,exist_ok=True)
    c=sqlite3.connect(_DB_PATH,timeout=10)
    c.execute("PRAGMA journal_mode=WAL");return c
def _hash_task(t):return hashlib.sha256(t.encode()).hexdigest()[:16]
def _now_ts():return time.time()

def init():
    c=_get_db_conn()
    try:
        c.execute("CREATE TABLE IF NOT EXISTS causal_chain (id INTEGER PRIMARY KEY,chain_id TEXT,ts REAL,task_hash TEXT,task_text TEXT,dimensions TEXT,outcome REAL,corrected INTEGER DEFAULT 0,notes TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS dimension_beliefs (dim_id TEXT PRIMARY KEY,belief REAL DEFAULT 0.5,hit_count INTEGER DEFAULT 0,miss_count INTEGER DEFAULT 0,last_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS judgment_snapshots (id INTEGER PRIMARY KEY,chain_id TEXT UNIQUE,ts REAL,task_hash TEXT,task_text TEXT,dimensions TEXT,weights TEXT,answers TEXT,confidence TEXT,complexity TEXT,emotion_label TEXT,causal_has_history INTEGER DEFAULT 0,outcome_auto REAL,corrected INTEGER DEFAULT 0,verdict TEXT)")
        # Outcome Prediction 表 — 记录判断时的预期结果，供后续验证
        c.execute("""CREATE TABLE IF NOT EXISTS outcome_predictions (
            id INTEGER PRIMARY KEY,
            chain_id TEXT UNIQUE,
            predicted_action TEXT,
            predicted_consequence TEXT,
            expected_timeline TEXT,
            prediction_ts REAL,
            verified INTEGER DEFAULT 0,
            actual_action TEXT,
            actual_consequence TEXT,
            outcome_score REAL,
            verified_ts REAL,
            verifier TEXT)""")
        # 迁移：judgment_snapshots 新增字段（已有表不 ALTER TABLE，故手动加）
        for col, dtype in [("verdict", "TEXT")]:
            try:
                c.execute(f"ALTER TABLE judgment_snapshots ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        for d in DIMS:c.execute("INSERT OR IGNORE INTO dimension_beliefs (dim_id,belief) VALUES (?,0.5)",(d,))
        c.commit()
    finally:c.close()

def snapshot_judgment(chain_id,task_text,dimensions,weights,result,complexity):
    """Frozen Snapshot: judgment调用时立即落盘，同时记录causal_chain"""  
    task_hash=_hash_task(task_text);now=_now_ts()
    answers=result.get("answers",{});emotion=result.get("emotion",{});curiosity=result.get("curiosity",{})
    dim_conf=result.get("dim_confidence",{});confidence={d:dim_conf.get(d,0.5) for d in dimensions}
    emotion_label=(emotion.get("detected_emotions",[""])[0] or "") if isinstance(emotion,dict) else ""
    causal_hist=1 if curiosity.get("has_gap") else 0
    verdict_text = result.get("verdict", "")  # 新增：记录verdict用于后续预测
    c=_get_db_conn()
    try:
        c.execute("INSERT OR REPLACE INTO judgment_snapshots (chain_id,ts,task_hash,task_text,dimensions,weights,answers,confidence,complexity,emotion_label,causal_has_history,verdict) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (chain_id,now,task_hash,task_text[:500] or "",json.dumps(dimensions,ensure_ascii=False),json.dumps(weights,ensure_ascii=False),json.dumps(answers,ensure_ascii=False),json.dumps(confidence,ensure_ascii=False),complexity,emotion_label,causal_hist,verdict_text[:300] or ""))
        c.execute("INSERT INTO causal_chain (chain_id,ts,task_hash,task_text,dimensions,outcome) VALUES (?,?,?,?,?,NULL)",
            (chain_id,now,task_hash,task_text[:300] or "",json.dumps({"dims":dimensions,"weights":weights},ensure_ascii=False)))
        c.execute("DELETE FROM causal_chain WHERE id NOT IN (SELECT id FROM causal_chain ORDER BY ts DESC LIMIT ?)",(MAX_CHAIN_RECORDS,))
        c.commit()
        # 【新】Outcome Prediction: 从verdict自动提取推荐行动
        if verdict_text:
            try:
                auto_predict_from_verdict(chain_id, verdict_text)
            except Exception as ex:
                _logger.debug(f"[outcome] predict skip: {ex}")
        _logger.debug(f"[snapshot] {chain_id} dims={len(dimensions)}")
        return True
    except Exception as e:
        _logger.warning(f"[snapshot] failed: {e}");return False
    finally:c.close()

def receive_verdict(chain_id=None,task_text=None,correct=True,notes="",
                      actual_action="", actual_consequence="", outcome_score=None, verifier="user"):
    """
    接收事后验证，更新维度信念，触发三个闭环hook。
    
    新增 outcome 验证参数（outcome_score 非空时触发 verify_outcome）:
    - actual_action: 实际采取了什么行动
    - actual_consequence: 实际后果描述
    - outcome_score: 0.0~1.0（None则用correct推断）
    - verifier: "user" / "system" / "time"
    """  
    c=_get_db_conn()
    try:
        target=None
        if chain_id:
            r=c.execute("SELECT id,dimensions FROM causal_chain WHERE chain_id=? AND corrected=0",(chain_id,)).fetchone()
            if r: target=r
        elif task_text:
            r=c.execute("SELECT id,dimensions FROM causal_chain WHERE task_hash=? AND corrected=0 ORDER BY ts DESC LIMIT 1",(_hash_task(task_text),)).fetchone()
            if r: target=r
        if not target: return {"updated":False,"reason":"no_record_found"}
        rec_id,dims_json=target;dims_data=json.loads(dims_json);correction=1.0 if correct else -1.0;changes={}
        for dim_id in dims_data.get("dims",[]):
            row=c.execute("SELECT belief,hit_count,miss_count FROM dimension_beliefs WHERE dim_id=?",(dim_id,)).fetchone()
            if not row: continue
            b,h,m=row;delta=max(-MAX_DELTA,min(MAX_DELTA,BELIEF_DECAY*correction));nb=max(SAT_LOW,min(SAT_HIGH,b+delta))
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
            _logger.debug(f"[self_evolver] recorded outcome: correct={correct}")
        except Exception as e:
            _logger.debug(f"[self_evolver] record_outcome skip: {e}")
        
        # 【闭环Step3.1】evolution_validator 验证追踪
        try:
            from evolver.evolution_validator import add_verdict_to_evolution_tracking
            add_verdict_to_evolution_tracking(1 if correct else 0)
        except Exception as e:
            _logger.debug(f"[evolution_validator] skip: {e}")
        
        # 【闭环Step3.2】InsightTracker: 记录 verdict 结果
        try:
            from judgment.insight_tracker import insight_tracker
            insight_tracker().record_verdict(
                chain_id=chain_id or "",
                correct=correct,
                dimensions=dims_data.get("dims", [])
            )
        except Exception:
            pass
        # 【闭环Step1】judgment → causal_memory
        _trigger_causal_memory(chain_id,task_text,dims_data.get("dims",[]),dims_data.get("weights",{}),correct,notes,1.0 if correct else 0.0)
        
        # Stop Hook: 捕获verdict行为
        try:
            from judgment.stop_hook import capture_verdict
            capture_verdict(chain_id, correct, notes)
        except Exception:
            pass
        
        # 【新】Outcome Verification: 当提供 actual_outcome 时 → verify_outcome
        if actual_action or actual_consequence or outcome_score is not None:
            try:
                verify_result = verify_outcome(
                    chain_id=chain_id,
                    actual_action=actual_action,
                    actual_consequence=actual_consequence,
                    outcome_score=outcome_score,
                    verifier=verifier
                )
                _logger.info(f"[outcome] verified: {chain_id} score={verify_result.get('score')}")
            except Exception as ex:
                _logger.debug(f"[outcome] verify skip: {ex}")

        _logger.info(f"[verdict] chain={chain_id} correct={correct} dims={list(changes.keys())}")
        return {"updated":True,"chain_id":chain_id,"changes":changes}
    finally:c.close()

def _trigger_fitness(chain_id,task_text,correct,changes):
    try:
        from judgment.fitness_baseline import FitnessBaseline
        FitnessBaseline().record(chain_id,task_text,correct,changes)
    except Exception as e:_logger.debug(f"fitness trigger skip: {e}")
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
    except Exception as e2:_logger.debug(f"fitness_evolution trigger skip: {e2}")

def _trigger_curiosity(chain_id,task_text,correct,changes):
    try:
        from emotion_system.emotion_system import EmotionSystem
        es=EmotionSystem();es.detect_emotion(task_text,{"task":task_text,"dim_confidence":{},"meta":{}});pad=es.get_pad_state()
        from curiosity.curiosity_engine import trigger_from_verdict
        trigger_from_verdict(chain_id,task_text,correct,pad,changes)
    except Exception as e:_logger.debug(f"curiosity trigger skip: {e}")

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

        _logger.debug(f"[causal_memory] recorded verdict event_id={event_id}")
        return event_id
    except Exception as e:
        _logger.debug(f"[causal_memory] trigger skip: {e}")
        return None

def get_prior_adjustments()->Dict[str,float]:
    c=_get_db_conn()
    try:return {r[0]:r[1] for r in c.execute("SELECT dim_id,belief FROM dimension_beliefs")}
    finally:c.close()

def get_recent_chains(limit=10):
    c=_get_db_conn()
    try:return [{"chain_id":r[0],"ts":r[1],"task_text":r[2],"outcome":r[3],"corrected":bool(r[4])} for r in c.execute("SELECT chain_id,ts,task_text,outcome,corrected FROM causal_chain ORDER BY ts DESC LIMIT ?",(limit,)).fetchall()]
    finally:c.close()

def get_dimension_beliefs()->Dict[str,Dict[str,Any]]:
    c=_get_db_conn()
    try:return {r[0]:{"belief":r[1],"hit":r[2],"miss":r[3]} for r in c.execute("SELECT dim_id,belief,hit_count,miss_count FROM dimension_beliefs")}
    finally:c.close()

# ── 后台 verdict 监听器（Auto闭环核心）───────────────────────────────
# 监听 data/outcomes.jsonl，新outcome写入时自动触发 receive_verdict
# 轮询间隔：2秒，连续3次空读后退出（节省资源）

def _verdict_signal_listener():
    """后台线程：监听 outcomes.jsonl，自动调用 receive_verdict"""  
    empty_count=0
    while not _listener_stop.is_set():
        _listener_stop.wait(timeout=2)
        if _listener_stop.is_set(): break
        try:
            if not os.path.exists(_OUTCOMES_FILE): empty_count+=1; continue
            with open(_OUTCOMES_FILE,encoding="utf-8") as f:
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
                with open(_OUTCOMES_FILE,"w",encoding="utf-8") as f2:
                    f2.writelines(lines)
                _logger.info(f"[listener] verdict recorded for chain={chain_id}")
        except Exception as e:
            _logger.debug(f"[listener] poll error: {e}")
    _logger.info("[listener] stopped")

def start_verdict_listener():
    """启动后台 verdict 监听线程（幂等）"""  
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive(): return
    _listener_stop.clear()
    _listener_thread=threading.Thread(target=_verdict_signal_listener,daemon=True,name="verdict_listener")
    _listener_thread.start()
    _logger.info("[listener] started")

def stop_verdict_listener():
    """停止监听线程"""  
    _listener_stop.set()
    if _listener_thread: _listener_thread.join(timeout=3)
    _logger.info("[listener] stop requested")

def is_listener_active()->bool:
    return _listener_thread is not None and _listener_thread.is_alive()

# ── record_judgment wrapper（兼容 router.py 的调用方式）───────────────
# 旧接口: record_judgment(task_text, dimensions, weights, reasoning, outcome)
# 新实现: 内部调用 snapshot_judgment，同时写入 causal_chain + judgment_snapshots
def record_judgment(task_text, dimensions, weights, reasoning=None, outcome=None):
    chain_id = f"j_{int(time.time()*1000)}"
    dummy_result = {"answers": {}, "meta": {"reasoning": reasoning or {}}, "emotion": {}, "curiosity": {}, "dim_confidence": {}}
    snapshot_judgment(chain_id, task_text, dimensions, weights, dummy_result, "auto")
    return chain_id

# ── Outcome Prediction + Verification 层 ──────────────────────────────
# 核心思路：判断时记录"预期结果"，后续验证"实际结果"
# correct=True/False → 偏好信号（弱）
# predicted/actual outcome → 结果验证（强）

def predict_outcome(chain_id, predicted_action, predicted_consequence="", expected_timeline=""):
    """
    在 snapshot_judgment 后调用，记录系统对判断结果的预期。
    用途：后续 verify_outcome 对比 → 计算判断准确率
    
    Args:
        chain_id: 判断快照ID
        predicted_action: 推荐行动（从verdict提取，如"选A""留在原地"）
        predicted_consequence: 预期后果描述（可空）
        expected_timeline: 预期见效时间（可空，如"3个月内""1年后"）
    """
    c = _get_db_conn()
    try:
        c.execute("""INSERT OR REPLACE INTO outcome_predictions
            (chain_id, predicted_action, predicted_consequence, expected_timeline, prediction_ts, verified)
            VALUES (?, ?, ?, ?, ?, 0)""",
            (chain_id, predicted_action[:200], predicted_consequence[:500], expected_timeline[:100], _now_ts()))
        c.commit()
        _logger.debug(f"[outcome] predicted: {chain_id} → {predicted_action}")
        return True
    finally:
        c.close()


def verify_outcome(chain_id, actual_action, actual_consequence="", outcome_score=None, verifier="user"):
    """
    事后验证：用户/系统告知实际发生了什么。
    
    Args:
        chain_id: 判断快照ID
        actual_action: 实际采取了什么行动（与 predicted_action 对比）
        actual_consequence: 实际后果描述
        outcome_score: 0.0~1.0，结果符合预期的程度
            - 1.0: 完全符合（预测命中）
            - 0.5: 部分符合
            - 0.0: 完全不符
            - None: 自动从 action 匹配度计算
        verifier: "user" / "system" / "time"
    
    Returns:
        dict with: match (bool), score, correctness signal for evolver
    """
    c = _get_db_conn()
    try:
        row = c.execute("SELECT predicted_action, predicted_consequence FROM outcome_predictions WHERE chain_id=?",
                        (chain_id,)).fetchone()
        if not row:
            _logger.warning(f"[outcome] verify: chain_id={chain_id} not found, auto-create prediction record")
            c.execute("INSERT OR IGNORE INTO outcome_predictions (chain_id, verified) VALUES (?, 0)", (chain_id,))
            c.commit()
            predicted_action, predicted_consequence = "", ""
        else:
            predicted_action, predicted_consequence = row

        # 自动计算 outcome_score（action 匹配度）
        if outcome_score is None:
            if not actual_action:
                outcome_score = 0.5  # 无数据
            elif predicted_action and actual_action == predicted_action:
                outcome_score = 1.0  # 行动命中
            elif predicted_action and (predicted_action in actual_action or actual_action in predicted_action):
                outcome_score = 0.7  # 近似命中
            elif predicted_action:
                outcome_score = 0.3  # 未按预测行动
            else:
                outcome_score = 0.5  # 无预测，无法判断

        c.execute("""UPDATE outcome_predictions SET
            verified=1, actual_action=?, actual_consequence=?,
            outcome_score=?, verified_ts=?, verifier=?
            WHERE chain_id=?""",
            (actual_action[:200], actual_consequence[:500], outcome_score, _now_ts(), verifier, chain_id))
        c.commit()

        # correctness 信号（与旧 evolver 接口兼容）
        correct_signal = 1 if outcome_score >= 0.5 else 0

        # 【闭环】outcome_score 反馈到 evolver（强于 correct=True/False 二值信号）
        try:
            from judgment.self_evolover import EvolverScheduler
            _sch = EvolverScheduler()
            _sch.record_outcome(correct_signal)  # 1=正确, 0=错误
            _logger.debug(f"[evolver] outcome verified: correct={correct_signal}")
        except Exception as e:
            _logger.debug(f"[evolver] record_outcome skip: {e}")

        return {
            "chain_id": chain_id,
            "predicted_action": predicted_action,
            "actual_action": actual_action,
            "match": outcome_score >= 0.5,
            "score": outcome_score,
            "correct": correct_signal
        }
    finally:
        c.close()


def get_verification_stats() -> dict:
    """
    返回全局 outcome 验证统计 → 指导进化方向。
    
    Returns:
        {
            "total": N,
            "verified": M,
            "avg_score": 0.x,
            "by_dimension": {...},
            "weakest_dims": [...],
            "unverified_count": K
        }
    """
    c = _get_db_conn()
    try:
        total = c.execute("SELECT COUNT(*) FROM outcome_predictions").fetchone()[0]
        verified_rows = c.execute(
            "SELECT chain_id, outcome_score, verified FROM outcome_predictions WHERE verified=1"
        ).fetchall()
        verified = len(verified_rows)
        avg_score = sum(r[1] for r in verified_rows) / verified if verified else 0.0

        # 关联维度：join causal_chain → dimensions
        by_dim = {d: {"correct": 0, "total": 0} for d in DIMS}
        for row in verified_rows:
            cid, score, _ = row
            dims_row = c.execute("SELECT dimensions FROM causal_chain WHERE chain_id=?", (cid,)).fetchone()
            if dims_row:
                for dim in json.loads(dims_row[0]).get("dims", []):
                    if dim in by_dim:
                        by_dim[dim]["total"] += 1
                        by_dim[dim]["correct"] += 1 if score >= 0.5 else 0

        by_dimension = {}
        weakest = []
        for d, stats in by_dim.items():
            if stats["total"] > 0:
                acc = stats["correct"] / stats["total"]
                by_dimension[d] = {"accuracy": round(acc, 3), "n": stats["total"]}
                weakest.append((d, acc))
        weakest.sort(key=lambda x: x[1])

        return {
            "total": total,
            "verified": verified,
            "avg_score": round(avg_score, 3),
            "unverified_count": total - verified,
            "by_dimension": by_dimension,
            "weakest_dims": weakest[:3],  # 最弱的3个维度
            "strongest_dims": weakest[-3:][::-1] if weakest else []
        }
    finally:
        c.close()


def auto_predict_from_verdict(chain_id, verdict_text):
    """
    从 verdict 文本自动提取推荐行动 → 调用 predict_outcome。
    由 snapshot_judgment 调用，或在 receive_verdict 末尾调用。
    
    提取策略：
    1. 句号前的完整短句
    2. 引号内内容
    3. "建议/推荐/选/做/不要"后面的动作描述
    """
    import re
    if not verdict_text:
        return None
    v = verdict_text.strip()

    # 策略1: 引号内容（支持中/英双引号）
    extracted = None
    for lq, rq in [('\u201c', '\u201d'), ('"', '"'), ("'", "'")]:
        pattern = re.escape(lq) + r'(.+?)' + re.escape(rq)
        m = re.search(pattern, v)
        if m:
            extracted = m.group(1).strip()
            break
    if extracted:
        return predict_outcome(chain_id, extracted)

    # 策略2: "建议/推荐"后面
    for kw in ("建议", "推荐", "选", "做", "不要", "可", "应"):
        idx = v.find(kw)
        if idx >= 0:
            # 取kw后到句号/逗号之间的内容
            fragment = v[idx:].lstrip(kw)
            end = min(len(fragment), fragment.find("，") if "，" in fragment else len(fragment))
            end = min(end, fragment.find("。") if "。" in fragment else end)
            action = fragment[:end].strip()
            if action:
                return predict_outcome(chain_id, action)

    # 策略3: 直接取句号前的短句（不超过20字）
    for sep in ("。", "！", "？"):
        if sep in v:
            first_sentence = v.split(sep)[0].strip()
            if 2 <= len(first_sentence) <= 30:
                return predict_outcome(chain_id, first_sentence)

    # 兜底: 截取前20字
    if len(v) >= 2:
        return predict_outcome(chain_id, v[:20])
    return None
