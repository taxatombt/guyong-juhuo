#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life OS v3"""
import sys,argparse,re
from typing import Dict,Tuple
from dataclasses import dataclass
EH=70;EM=45
EB={"excitement":{"cognitive":+20,"social":+15,"physical":+10,"admin":+0},"joy":{"cognitive":+15,"social":+10,"physical":+10,"admin":+5},"anxiety":{"cognitive":-20,"social":+0,"physical":+20,"admin":+10},"sadness":{"cognitive":-10,"social":-10,"physical":+5,"admin":+5},"calm":{"cognitive":+10,"social":+0,"physical":+5,"admin":+5}}

@dataclass
class Task:
    n:str;cd:int=20;sd:int=20;pd:int=20;eb:int=20;tt:str="admin"
    @staticmethod
    def classify(n:str)->"Task":
        lo=n.lower();t=Task(n=n)
        if any(k in lo for k in ["写","bp","报告","分析","规划","策略","思考","开发","代码"]):t.cd=80;t.tt="cognitive"
        elif any(k in lo for k in ["见","会","电话","聊","客户","面试","谈判"]):t.sd=80;t.tt="social"
        elif any(k in lo for k in ["健","跑","瑜伽","运动","健身","游泳","骑车"]):t.pd=80;t.tt="physical"
        elif any(k in lo for k in ["妈妈","家人","朋友","放松","休息","冥想"]):t.eb=80;t.tt="emotional"
        return t

@dataclass
class LS:
    e:int;p:Dict[str,float];l:str
    @staticmethod
    def from_pad(e:int,p:Dict[str,float])->"LS":
        P,A,D=p.get("P",0),p.get("A",0),p.get("D",0)
        if P>.2 and A>.2 and D>.2:l="excitement"
        elif P<-.2 and A>.2 and D<-.2:l="anxiety"
        elif P>.2 and A<-.2:l="joy"
        elif P<-.2 and A<-.2:l="sadness"
        else:l="calm"
        return LS(e=e,p=p,l=l)

@dataclass
class ST:
    task:str;tt:str;can:bool;reason:str;rs:int;ts:str
    js:float=-1.0;verdict:str="";rank:int=0

def _dp(s:str)->Dict[str,float]:
    t=s.lower();P=A=D=0
    if any(k in t for k in ["开心","兴奋","愉悦","期待","满足","轻松","舒服"]):P+=.4
    if any(k in t for k in ["焦虑","低落","抑郁","疲惫","紧张","压力","难过","烦躁","不安","担心"]):P-=.4
    if any(k in t for k in ["兴奋","激动","紧张","心跳","期待","焦虑"]):A+=.4
    if any(k in t for k in ["平静","放松","慵懒","疲惫","低落"]):A-=.3
    if any(k in t for k in ["自信","掌控","坚定","主动","有把握"]):D+=.3
    if any(k in t for k in ["迷茫","犹豫","失控","被动","不确定","没信心"]):D-=.3
    return {"P":max(-1,min(1,P)),"A":max(-1,min(1,A)),"D":max(-1,min(1,D))}

def _ce(t:Task,s:LS)->Tuple[bool,str]:
    if t.cd>=70 and s.e<EM:return False,"精力不足"
    if t.sd>=70 and s.p.get("A",0)<.3:return False,"情绪未激活"
    return True,""

def _rs(t:Task,s:LS)->int:
    sc=50
    if t.cd>=70:sc+=30 if s.e>=EH else -10
    if t.sd>=70:sc+=20 if s.p.get("A",0)>=.3 else -20
    if t.pd>=70:sc+=15
    sc+=EB.get(s.l,{}).get(t.tt,0)
    return max(0,min(100,sc))

def _ts(t:Task)->str:
    if t.cd>=70:return "上午 (08:30-11:30)"
    if t.pd>=70:return "傍晚 (17:00-19:00)"
    if t.sd>=70:return "下午 (14:00-17:00)"
    return "灵活"

def rule_schedule(tasks,s):
    res=[]
    for tn in tasks:
        t=Task.classify(tn)
        can,reason=_ce(t,s)
        sc=_rs(t,s) if can else 0
        res.append(ST(task=tn,tt=t.tt,can=can,reason=reason,rs=sc,ts=_ts(t) if can else "延期"))
    res.sort(key=lambda x:(-x.can,-x.rs))
    for i,r in enumerate(res,1):r.rank=i
    return res

_JUHUO_READY=False
def _init():
    global _JUHUO_READY
    if _JUHUO_READY:return True
    try:
        import os,sys as s
        d=os.path.dirname(os.path.abspath(__file__));s.path.insert(0,d)
        from judgment.behavior_logger import log_agent_behavior,ActionChannel
        from llm_adapter import get_adapter,CompletionRequest
        _JUHUO_READY=True;return True
    except:return False

def _juhuo_rank(tasks,s,res):
    if not _init():
        print("  [juhuo] unavailable");return res
    try:
        from llm_adapter import get_adapter,CompletionRequest
        import re
        cm={"excitement":"兴奋","anxiety":"焦虑","joy":"愉悦","sadness":"低落","calm":"平静"}
        cn=cm.get(s.l,s.l)
        doable=[r for r in res if r.can]
        notdo=[r for r in res if not r.can]
        if not doable:
            print("  [juhuo] no doable tasks");return res
        tlist=",".join(tasks)
        task_lines="\n".join(f"  {i+1}. {r.task}" for i,r in enumerate(doable))
        prompt=f"""[任务]
精力{{s.e}}%，情绪{cn}。以下待办按优先级排序，给出理由：
{task_lines}
直接回答格式：
排序:[1,2,...]
理由:..."""
        adapter=get_adapter()
        if not adapter.is_configured():
            print("  [juhuo] MiniMax not configured");return res
        resp=adapter.complete(CompletionRequest(prompt=prompt,max_tokens=1500,temperature=0.5))
        raw=resp.content.strip() if resp.success else f"[API error: {resp.error}]"
        verdict=re.sub(r"<think>.*?</think>","",raw,flags=re.DOTALL).strip()
        if not verdict:verdict=raw[:200].strip()
        # Parse ranking: extract position numbers and map to task names
        scores={}
        # Find the 排序:[1,2,...] line and split to get position order
        rank_m=re.search(r"排序:\s*\[([^\]]+)\]",verdict)
        if rank_m:
            positions=[p.strip() for p in rank_m.group(1).split(",")]
            # Map each position to the matching task name from the verdict
            for pos_str in positions:
                try:
                    pos=int(pos_str)
                except:continue
                score=max(0.3,1.0-(pos-1)*0.15)
                # Find the task at this position in the verdict text
                # Look for task name mentioned near the position number
                # Pattern: "1. 写报告" or "1. **写报告**" in the verdict
                for r in doable:
                    if r.task not in scores and r.task in verdict:
                        scores[r.task]=score
                        r.verdict=verdict;r.js=score
                        break
        for r in doable:
            if r.task not in scores:
                r.verdict=verdict;r.js=0.6
        doable.sort(key=lambda x:x.js,reverse=True)
        for i,r in enumerate(doable,1):r.rank=i
        for i,r in enumerate(notdo,len(doable)+1):r.rank=i
        try:
            from judgment.behavior_logger import log_agent_behavior,ActionChannel
            log_agent_behavior(task_text=f"LifeOS:{tlist}",channel=ActionChannel.JUDGMENT,verdict=verdict,confidence=0.7,tool_calls=[],execution_result=f"rank:{[r.task for r in doable]}",outcome_score=-1.0,user_id="default")
        except:pass
        print(f"  [juhuo] verdict: {verdict[:80]}")
        return doable+notdo
    except Exception as e:
        print(f"  [juhuo] error: {e}");return res

def _print(res,s,jmode):
    m="juhuo"if jmode else"rules"
    cm={"excitement":"兴奋","anxiety":"焦虑","joy":"愉悦","sadness":"低落","calm":"平静"}
    ec=cm.get(s.l,s.l)
    print();print("="*62)
    print(f"  Life OS v3  [{m} mode]")
    print("="*62)
    print(f"  energy: {s.e}%  |  emotion: {ec}  |  tasks: {len(res)}")
    print("-"*62)
    print("{:<4} {:<18} {:<8} {:<6} {:<6}  {}".format("#","task","type","rule","jconf","time_slot"))
    print("-"*62)
    for r in res:
        st="[OK]"if r.can else"[DELAY]"
        js=f"{r.js:.0%}"if r.js>=0 else"-" 
        print("{:<4} {:<18} {:<8} {:<6} {:<6}  {} {}".format(r.rank,r.task[:16],r.tt,r.rs,js,r.ts,st))
    print()
    if s.l=="anxiety":print("  [advice] anxiety -> do low-cognitive or exercise first")
    elif s.l=="excitement" and s.e>=EH:print("  [advice] high energy+excitement -> best day for deep work")
    elif s.e<EM:print(f"  [advice] low energy ({s.e}%) -> defer cognitive tasks")
    elif s.e>=EH:print(f"  [advice] good energy ({s.e}%) -> deep work day")
    verdicts=[r.verdict for r in res[:4]if r.verdict]
    if verdicts:print();print("  [juhuo verdicts]");[print(f"    - {v[:70]}")for v in verdicts]
    print()

def main():
    p=argparse.ArgumentParser(description="Life OS v3")
    p.add_argument("tasks",nargs="*",help="Tasks (slash/comma separated)")
    p.add_argument("--energy",type=int,default=60,help="Energy 0-100")
    p.add_argument("--emotion",help="PAD e.g. P=0.3,A=0.5,D=0.6")
    p.add_argument("--juhuo",action="store_true",help="Use juhuo judgment (v3)")
    p.add_argument("--today",help="Today description (auto emotion infer)")
    a=p.parse_args()
    raw=a.tasks
    if not raw:
        print("Usage: python life_os.py <tasks> [--energy N] [--emotion P=X,A=Y,D=Z] [--juhuo]")
        print("  python life_os.py 写报告/健身/见客户 --energy 65 --juhuo");return
    tasks=[]
    for t in raw:
        tasks.extend([x.strip()for x in t.replace("、","/").replace(",","/").split("/")if x.strip()])
    if a.today:
        pad=_dp(a.today);e=60
        for kw,v in [("非常累",20),("很累",30),("比较累",45),("还行",60),("状态不错",75),("精力充沛",90)]:
            if kw in a.today:e=v;break
    elif a.emotion:
        pad={"P":0,"A":0,"D":0}
        for pt in a.emotion.replace(" ","").split(","):
            if"="in pt:k,v=pt.split("=",1);pad[k.strip()]=float(v.strip())
        e=a.energy
    else:
        pad={"P":0,"A":0,"D":0};e=a.energy
    s=LS.from_pad(e,pad)
    res=rule_schedule(tasks,s)
    if a.juhuo:print("  [using juhuo judgment...]");res=_juhuo_rank(tasks,s,res)
    _print(res,s,a.juhuo)

if __name__=="__main__":main()
