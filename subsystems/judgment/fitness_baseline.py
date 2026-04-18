#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identity Fitness Baseline for JuHuo"""
import json, math, hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict

_JD = Path(__file__).parent.parent / "data" / "judgment_data"
_BL = _JD / "fitness_baseline.json"
_SN = _JD / "fitness_snapshots"
_LG = _JD / "fitness_check_log.jsonl"
_SN.mkdir(parents=True, exist_ok=True)
_DIMS = ["cognitive","game_theory","economic","dialectical","emotional","intuitive","moral","social","temporal","metacognitive"]

@dataclass
class JP:
    dw: Dict[str,float]; ac: float; er: float; rt: str; so: float; tf: float; ms: float; tt: List[str]; sc: int
    sid: str=""; pl: str=""; ca: str=field(default_factory=lambda: datetime.now().isoformat())
    def to_dict(self): return asdict(self)
    @staticmethod
    def from_dict(d):
        # 兼容旧版字段名（dimension_weights → dw 等）
        alias = {
            "dimension_weights": "dw", "avg_confidence": "ac", "emotional_reliance": "er",
            "risk_tolerance": "rt", "social_orientation": "so", "temporal_focus": "tf",
            "moral_strictness": "ms", "typical_task_types": "tt", "sample_count": "sc",
            "snapshot_id": "sid", "period_label": "pl", "created_at": "ca",
        }
        return JP(**{alias.get(k, k): v for k, v in d.items()})
    def sim(self, o):
        v1 = [self.dw.get(d,0) for d in sorted(self.dw)]
        v2 = [o.dw.get(d,0) for d in sorted(o.dw)]
        if not v1 or len(v1)!=len(v2): return 0.0
        dot = sum(a*b for a,b in zip(v1,v2))
        n1,n2 = math.sqrt(sum(a*a for a in v1)), math.sqrt(sum(a*a for a in v2))
        return dot/(n1*n2) if n1 and n2 else 0.0

class FitnessBaseline:
    """Builds from actual usage — adapts to whoever uses it.
    No preset identity. The user is defined by how they actually judge."""

    def __init__(self):
        _JD.mkdir(parents=True, exist_ok=True)
        if not _BL.exists(): _BL.write_text("{}", encoding="utf-8")
        if not _LG.exists(): _LG.write_text("", encoding="utf-8")

    def _load(self):
        try:
            d = json.loads(_BL.read_text(encoding="utf-8"))
            return JP.from_dict(d) if d else None
        except: return None

    def _save(self, p): _BL.write_text(json.dumps(p.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _snap(self, p):
        p.sid = hashlib.md5(p.ca.encode()).hexdigest()[:12]
        (_SN / f"{p.sid}.json").write_text(json.dumps(p.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _log(self, r): open(_LG, "a", encoding="utf-8").write(json.dumps(r, ensure_ascii=False)+"\n")

    def _dims(self, t):
        m = {"cognitive":["分析","思考","认知","验证"],"game_theory":["博弈","玩家","合作"],"economic":["成本","收益","赚钱","创业","辞职"],"emotional":["焦虑","情绪","担心"],"intuitive":["直觉","感觉"],"moral":["底线","道德"],"social":["关系","人际"],"temporal":["长期","短期","辞职","创业"],"metacognitive":["反思","复盘"]}
        return [k for k,v in m.items() if any(x in t for x in v)][:4]

    def _avgconf(self):
        try:
            f = Path(__file__).parent.parent / "self_model.json"
            if f.exists():
                d = json.loads(f.read_text(encoding="utf-8"))
                n = d.get("total_decisions", 0)
                if n > 0: return min(0.95, 0.4 + n * 0.01)
        except: pass
        return 0.6

    def build_baseline(self):
        log = Path(__file__).parent.parent / "action_log.jsonl"
        jj = []
        if log.exists():
            try:
                for line in log.read_text(encoding="utf-8").strip().splitlines():
                    try: jj.append(json.loads(line))
                    except: continue
            except: pass
        dc = defaultdict(int)
        for j in jj:
            for d in self._dims(j.get("judgment_task", "")): dc[d] += 1
        t = sum(dc.values())
        dw = {d: (dc.get(d,0)/t if t>0 else 1.0/10) for d in _DIMS}
        rk = ["风险","危险","焦虑","创业","辞职"]
        rc = sum(1 for j in jj if any(k in j.get("judgment_task","") for k in rk))
        ratio = rc/len(jj) if jj else 0
        rt = "very_high" if ratio>0.5 else "high" if ratio>0.3 else "medium"
        tt_d = {"创业":["创业","辞职"],"人际":["关系"],"职业":["工作","跳槽"]}
        tt = [t for t,kw in tt_d.items() if any(k in j.get("judgment_task","") for j in jj for k in kw)]
        ds = sorted(set(j.get("judgment_id","")[:8] for j in jj if j.get("judgment_id")))
        pl = (f"{ds[0]}~{ds[-1]}" if ds else "unknown")
        p = JP(dw=dw, ac=self._avgconf(), er=dw.get("emotional",0.2), rt=rt,
               so=dw.get("social",0.1), tf=dw.get("temporal",0.1), ms=dw.get("moral",0.5),
               tt=tt[:5], sc=len(jj), pl=pl)
        self._save(p); self._snap(p); return p

    def check_fitness(self):
        bl = self._load()
        if not bl: return {"fitness_score": 0.0, "status": "no_baseline", "recommendation": "run build_baseline first"}
        snaps = sorted(_SN.glob("*.json"), key=lambda p: p.name)
        cu = bl
        if snaps:
            try: cu = JP.from_dict(json.loads(snaps[-1].read_text(encoding="utf-8")))
            except: pass
        fs = bl.sim(cu)
        dr = [{"dim": d, "baseline": round(bl.dw.get(d,0),3), "current": round(cu.dw.get(d,0),3), "drift": round(cu.dw.get(d,0)-bl.dw.get(d,0),3)}
              for d in _DIMS if abs(cu.dw.get(d,0)-bl.dw.get(d,0)) > 0.15]
        st = "critical" if fs<0.6 or len(dr)>=3 else "drifted" if fs<0.75 or len(dr)>=1 else "healthy"
        rec = "严重漂移，建议回滚" if st=="critical" else "检测到偏差，建议检查进化方向" if st=="drifted" else "Fitness正常，保持你的判断特征"
        r = {"fitness_score": round(fs,3), "status": st, "drifted_dims": dr, "baseline_period": bl.pl, "current_period": cu.pl, "recommendation": rec}
        self._log(r); return r

    def rollback(self):
        for sp in sorted(_SN.glob("*.json"), key=lambda p: p.name, reverse=True):
            try:
                p = JP.from_dict(json.loads(sp.read_text(encoding="utf-8")))
                self._save(p); return {"success": True, "snapshot_id": p.sid, "period": p.pl}
            except: continue
        return {"success": False}

    def summary(self):
        bl = self._load(); snaps = sorted(_SN.glob("*.json")); ft = self.check_fitness()
        return {"has_baseline": bl is not None, "baseline_period": bl.pl if bl else None, "snapshot_count": len(snaps), "status": ft["status"], "score": ft["fitness_score"]}

    def record_from_verdict(self, chain_id: str, task_text: str,
                            correct: bool, notes: str = "",
                            changes: Optional[Dict] = None) -> Dict:
        """
        事后验证 → 记录到 fitness 检查日志 + 触发漂移检测。
        由 closed_loop.receive_verdict() 在信念更新后调用。
        """
        entry = {
            "type": "verdict",
            "chain_id": chain_id,
            "task": task_text[:200] if task_text else "",
            "correct": correct,
            "notes": notes[:200] if notes else "",
            "timestamp": datetime.now().isoformat(),
            "changes": {k: round(v["delta"], 4) for k, v in (changes or {}).items()},
        }
        self._log(entry)

        # 每5条 verdict 自动做一次 fitness 检查
        try:
            log_lines = _LG.read_text(encoding="utf-8").strip().splitlines()
            verdict_count = sum(1 for l in log_lines if '"type": "verdict"' in l)
            if verdict_count > 0 and verdict_count % 5 == 0:
                drift_result = self.check_fitness()
                entry["fitness_check"] = drift_result
        except Exception:
            pass

        return entry
