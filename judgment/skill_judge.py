"""
Darwin Skill Scoring Engine
来源: alchaincyf/darwin-skill (GitHub啃读落地)
8维度评估SKILL.md质量，总分100分
"""

from __future__ import annotations
import json, os, re, csv, math
from datetime import datetime
from pathlib import Path
from typing import Tuple

DIMENSIONS = [
    {"id":1,"name":"Frontmatter质量","weight":8,"type":"structure"},
    {"id":2,"name":"工作流清晰度","weight":15,"type":"structure"},
    {"id":3,"name":"边界条件覆盖","weight":10,"type":"structure"},
    {"id":4,"name":"检查点设计","weight":7,"type":"structure"},
    {"id":5,"name":"指令具体性","weight":15,"type":"structure"},
    {"id":6,"name":"资源整合度","weight":5,"type":"structure"},
    {"id":7,"name":"整体架构","weight":15,"type":"effect"},
    {"id":8,"name":"实测表现","weight":25,"type":"effect"},
]
WEIGHTS = {d["id"]:d["weight"] for d in DIMENSIONS}

def _fm(t):
    m=re.match(r"^---\n.*?\n---\n",t,re.DOTALL)
    return t[m.end():] if m else t

def _norm(t):
    t=re.sub(r"\s+"," ",t); return t.strip()

# ---- 8个评分函数 ----
def score_frontmatter(c):
    s,reasons=5,[]
    fm=re.match(r"^---\n(.*?)\n---",c,re.DOTALL)
    if not fm: return 2,"缺frontmatter"
    f=fm.group(1)
    if len(f)>1024: s-=1;reasons.append("fm>1024B")
    elif len(f)<80: s-=1;reasons.append("fm<80B")
    n=re.search(r"^name:\s*(.+)$",f,re.MULTILINE)
    if n and n.group(1).strip() not in("...","TODO",""): s+=2;reasons.append("name规范")
    else: s-=2;reasons.append("name缺失/占位")
    d=re.search(r'^description:\s*["\'](.+?)["\']',f,re.MULTILINE)
    if d:
        desc=d.group(1).lower()
        has_t=any(kw in desc for kw in["when","触发","适用","使用场景","当用户"])
        has_a=any(kw in desc for kw in["做","帮助","实现","优化","评估","does","helps"])
        if has_t and has_a: s+=2;reasons.append("desc含触发+动作")
        elif has_a: s+=1;reasons.append("desc含动作")
        else: s-=1;reasons.append("desc缺触发")
    else: s-=3;reasons.append("缺description")
    return max(1,min(10,s)),"; ".join(reasons)

def score_workflow(c):
    s,reasons=5,[]
    body=_fm(c)
    n=re.findall(r"(?:Phase|Step|阶段|步骤)\s*[\d:：.、]+",body)
    li=re.findall(r"(?:^|\n)\s*[-*]\s+\S",body)
    if len(n)>=3: s+=3;reasons.append(f"{len(n)}个步骤")
    elif len(n)>=1: s+=1;reasons.append(f"{len(n)}步骤")
    elif len(li)>=3: s+=1;reasons.append(f"{len(li)}列表项")
    else: s-=2;reasons.append("缺清晰步骤")
    io=len(re.findall(r"(?:输入|output|返回|input)[:：]\s*\S",body))
    if io>=2: s+=1;reasons.append(f"{io}个IO")
    elif io==1: pass
    else: s-=1;reasons.append("缺IO规格")
    return max(1,min(10,s)),"; ".join(reasons)

def score_boundary(c):
    s,reasons,body=5,[],_fm(c)
    ps=[(r"(?:如果|if).*?(?:失败|fail|error|异常)","条件失败"),
        (r"(?:否则|else|fallback|备选)","fallback"),
        (r"(?:异常|exception|try.*except)","异常处理"),
        (r"(?:边界|edge.*case|boundary)","边界case"),
        (r"(?:超时|timeout)","超时"),
        (r"(?:缺失|missing|not found)","缺失处理")]
    found=[l for p,l in ps if re.search(p,body,re.IGNORECASE)]
    if len(found)>=4: s+=3;reasons.append(f"异常{len(found)}类")
    elif len(found)>=2: s+=1;reasons.append(f"异常{len(found)}类")
    elif found: pass
    else: s-=2;reasons.append("缺异常处理")
    return max(1,min(10,s)),"; ".join(reasons)

def score_checkpoint(c):
    s,reasons,body=5,[],_fm(c)
    ps=[(r"(?:确认|confirm|verify|验证)","确认验证"),
        (r"(?:暂停|pause|stop)","暂停点"),
        (r"(?:人类|human|用户确认)","人机确认"),
        (r"(?:安全|unsafe|danger)","安全检查"),
        (r"(?:门控|guard|gate)","门控")]
    found=[l for p,l in ps if re.search(p,body,re.IGNORECASE)]
    if len(found)>=3: s+=3;reasons.append(f"检查点{len(found)}类")
    elif len(found)>=1: s+=1;reasons.append(f"检查点{len(found)}")
    else: s-=2;reasons.append("缺检查点")
    return max(1,min(10,s)),"; ".join(reasons)

def score_specificity(c):
    s,reasons,body=5,[],_fm(c)
    norm=re.sub(r"[#*`>_~\[\]]","",body); norm=re.sub(r"\s+"," ",norm).strip()
    vague=re.findall(r"\b(?:适当|可能|也许|大概|差不多|看看|试试|尽量)\b",norm)
    if len(vague)>=5: s-=3;reasons.append("模糊词"+str(len(vague)))
    elif vague: s-=1;reasons.append("模糊词"+str(len(vague)))
    spec=re.findall(r"(?:python|bash|git|api|http|sql|json|yaml|curl|wget)",body,re.I)
    if len(spec)>=5: s+=2;reasons.append("术语"+str(len(spec)))
    elif spec: s+=1
    code=re.findall(r"```[\s\S]*?```",body)
    if code: s+=1;reasons.append(str(len(code))+"个代码块")
    return max(1,min(10,s)),"; ".join(reasons) if reasons else "中等"

def score_resource(c):
    s,reasons,body=5,[],_fm(c)
    refs=re.findall(r"(?:references?|scripts?|assets?)[:：]\s*\S",body,re.I)
    if refs: s+=1;reasons.append(str(len(refs))+"引用")
    paths=re.findall(r"(?:skills?/|scripts?/|assets/)",body)
    if paths: s+=1;reasons.append(str(len(paths))+"路径引用")
    gh=re.findall(r"github\.com/[^\s)]+",body)
    if gh: s+=1;reasons.append(str(len(gh))+"GH链接")
    return max(1,min(10,s)),"; ".join(reasons) if reasons else "基础"

def score_architecture(c):
    s,reasons,body=5,[],_fm(c)
    if len(c)>15000: s-=2;reasons.append("过长>15KB")
    elif len(c)>8000: s-=1;reasons.append("较长")
    elif len(c)<500: s-=1;reasons.append("过短")
    h1=len(re.findall(r"^# ",body,re.MULTILINE))
    h2=len(re.findall(r"^## ",body,re.MULTILINE))
    if h1>=3 and h2>=5: s+=2;reasons.append("层级h1="+str(h1)+"h2="+str(h2))
    elif h1>=1: s+=1
    else: s-=1;reasons.append("缺层级")
    tbl=len(re.findall(r"\|[^|]+\|",body))
    if tbl>=3: s+=1;reasons.append(str(tbl)+"个表格")
    dup=len(re.findall(r"(.{50,})\n\1",body))
    if dup: s-=1;reasons.append("重复"+str(dup)+"处")
    return max(1,min(10,s)),"; ".join(reasons)

def score_actual(c):
    s,reasons=5,[]
    body=_fm(c)
    actionable=re.findall(r"(?:调用|执行|运行|使用|读取|写入|打开)\s+\S",body)
    if len(actionable)>=5: s+=3;reasons.append(str(len(actionable))+"可执行动作")
    elif actionable: s+=1
    ex=re.findall(r"(?:示例|example|例子|例如)[:：]",body,re.I)
    if len(ex)>=3: s+=2;reasons.append(str(len(ex))+"示例")
    elif ex: s+=1
    return max(1,min(10,s)),"; ".join(reasons) if reasons else "干跑基础"

def judge_skill_quality(skill_path):
    path=Path(skill_path)
    skill_file=path/"SKILL.md"
    if not skill_file.exists(): skill_file=path
    content=skill_file.read_text(encoding="utf-8")
    scores={}; reasons={}
    scores[1],reasons[1]=score_frontmatter(content)
    scores[2],reasons[2]=score_workflow(content)
    scores[3],reasons[3]=score_boundary(content)
    scores[4],reasons[4]=score_checkpoint(content)
    scores[5],reasons[5]=score_specificity(content)
    scores[6],reasons[6]=score_resource(content)
    scores[7],reasons[7]=score_architecture(content)
    scores[8],reasons[8]=score_actual(content)
    total=sum(scores[d]*WEIGHTS[d] for d in WEIGHTS)/10.0
    weakest=min(scores,key=scores.get)
    weak_points=[]; suggestions=[]
    for dim_id in sorted(scores):
        if scores[dim_id]<=4:
            dim_name=next(x["name"] for x in DIMENSIONS if x["id"]==dim_id)
            weak_points.append({"id":dim_id,"name":dim_name,"score":scores[dim_id],"reason":reasons[dim_id]})
            suggestions.append("D"+str(dim_id)+" "+dim_name+": "+reasons[dim_id])
    return {
        "skill_path": skill_file.parent.name,
        "total_score": round(total,1),
        "structure_score": round(sum(scores[d]*WEIGHTS[d] for d in range(1,7))/10.0,1),
        "effect_score": round(sum(scores[d]*WEIGHTS[d] for d in range(7,9))/10.0,1),
        "dimension_scores":[{"id":d,**next(x for x in DIMENSIONS if x["id"]==d),"score":scores[d],"reason":reasons[d]} for d in sorted(scores)],
        "weak_points": weak_points,
        "suggestions": suggestions,
    }

def list_skills(base_dirs):
    found=[]
    for base in base_dirs:
        base_p=Path(base)
        if not base_p.exists(): continue
        for p in base_p.rglob("SKILL.md"):
            found.append(str(p.parent))
    return found

def score_all_skills(base_dirs):
    results=[]
    for skill_dir in list_skills(base_dirs):
        try: results.append(judge_skill_quality(skill_dir))
        except Exception as e: results.append({"skill_path":Path(skill_dir).name,"error":str(e)})
    results.sort(key=lambda x: x.get("total_score",0))
    return results

def print_report(results):
    print("\n"+"="*60)
    print("  Darwin Skill Quality Report")
    print("="*60)
    for r in results:
        if "error" in r: print("  [ERR] "+r["skill_path"]+": "+r["error"]); continue
        print("  ["+str(r["total_score"]).ljust(5)+"/100] "+r["skill_path"])
        if r.get("weak_points"):
            for wp in r["weak_points"]: print("         - D"+str(wp["id"])+" "+wp["name"]+": "+wp["reason"])
    scored=[r for r in results if "total_score" in r]
    if scored: print("\n  平均分: "+str(sum(x["total_score"] for x in scored)/len(scored))[:5]+"/100")
    print("="*60)

if __name__=="__main__":
    import sys
    dirs=sys.argv[1:] if len(sys.argv)>1 else ["./skills","./workspace_tools"]
    results=score_all_skills(dirs)
    print_report(results)
