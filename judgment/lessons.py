#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lessons System v2 - 因果链教训层
P2-3: confidence 时间衰减 (last_reinforced + exp decay, 半衰期30天)
P2-2: 50条种子教训 (9个领域)
P2-1: LLM 语义提取 (_llm_extract_lessons)
"""
import sqlite3, json, hashlib, math, re
from datetime import datetime, timedelta
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data" / "judgment_data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB = _DATA_DIR / "juhuo.db"

_DECAY_RATE = math.log(2) / 30
_MIN_CONFIDENCE = 0.1
_DEFAULT_CONFIDENCE = 0.7


# ===== MiniMind Rep Penalty（来源：train_grpo.py / train_ppo.py）=====
def rep_penalty(text: str, n: int = 3, cap: float = 0.5) -> float:
    """
    检测文本重复率，返回惩罚值 [0.0, cap]。
    n-gram 重复率越高，惩罚越大。
    中文：按字符滑动窗口；英文：按单词。
    用于判断输出是否陷入循环，驱动 self_model 更新。
    """
    if not text or len(text) < n:
        return 0.0
    # 字符级分词（覆盖所有Unicode字符，n-gram滑动窗口）
    chars = list(text.lower())
    grams = ["".join(chars[i : i + n]) for i in range(len(chars) - n + 1)]
    if not grams:
        return 0.0
    repeat_ratio = (len(grams) - len(set(grams))) / len(grams)
    return min(cap, repeat_ratio * cap * 2)


def is_repetitive(text: str, threshold: float = 0.3) -> bool:
    """判断文本是否重复（rep_penalty >= threshold）"""
    return rep_penalty(text, n=3, cap=0.5) >= threshold

# Column names for lessons table (20 columns, matching actual DB schema)
_LESSON_COLS = [
    'id','lesson_type','domain','pattern','root_cause','correction',
    'positive_cases','negative_cases','hit_count','miss_count',
    'confidence','source','tags','verified','instance_signature',
    'created_at','updated_at','last_reinforced','times_applied','user_id'
]

LESSONS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS lessons (\n"
    "    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    lesson_type     TEXT    NOT NULL,\n"
    "    domain          TEXT    NOT NULL,\n"
    "    pattern         TEXT    NOT NULL,\n"
    "    root_cause      TEXT    NOT NULL,\n"
    "    correction      TEXT    NOT NULL,\n"
    "    positive_cases  INTEGER DEFAULT 0,\n"
    "    negative_cases  INTEGER DEFAULT 0,\n"
    "    hit_count       INTEGER DEFAULT 0,\n"
    "    miss_count      INTEGER DEFAULT 0,\n"
    "    confidence      REAL    DEFAULT 0.7,\n"
    "    source          TEXT    DEFAULT 'seed',\n"
    "    tags            TEXT,\n"
    "    verified        INTEGER DEFAULT 0,\n"
    "    instance_signature TEXT,\n"
    "    created_at      TEXT    NOT NULL,\n"
    "    updated_at      TEXT,\n"
    "    last_reinforced TEXT,\n"
    "    times_applied   INTEGER DEFAULT 0,\n"
    "    user_id         TEXT    DEFAULT 'default'\n"
    ");\n"
    "CREATE TABLE IF NOT EXISTS lesson_extract_log (\n"
    "    id          INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    chain_id    TEXT    NOT NULL,\n"
    "    lesson_type TEXT,\n"
    "    domain      TEXT,\n"
    "    pattern     TEXT,\n"
    "    root_cause  TEXT,\n"
    "    correction  TEXT,\n"
    "    llm_raw     TEXT,\n"
    "    created_at  TEXT    NOT NULL\n"
    ");"
)

_AUTO_EXTRACT_RULES = [
    (r"all\s*in",              "warning",  "检测到all in冒险倾向"),
    (r"焦虑|担心|害怕",           "causal",   "检测到情绪性决策"),
    (r"后悔|早知道|如果当初",     "causal",   "检测到事后聪明偏差"),
    (r"别人.*赚钱|FOMO",         "pattern",  "检测到从众/情绪驱动"),
    (r"低估|忽视|只.*而",        "bias",     "检测到认知偏差"),
    (r"买房|卖股|创业|辞职|跳槽|分手|移民", "pattern", "检测到重大决策"),
]

_DOMAIN_KEYWORDS = {
    "investment":  ["炒股","股票","基金","投资","买房","all in","止损","全仓","满仓"],
    "career":      ["辞职","跳槽","裸辞","offer","薪资","晋升","打工","创业","副业","裁员"],
    "relationship":["分手","离婚","复合","结婚","相亲","恋爱","婆媳","伴侣","感情","单身"],
    "family":      ["父母","孩子","子女","家庭","亲子","养老"],
    "migration":   ["移民","迁徙","回国","定居","迁移","留学","永居"],
    "health":      ["身体","健康","锻炼","疾病","医院","体检","减肥"],
    "education":  ["读书","学习","考证","考研","读研","读博","培训","课程","学历","文凭"],
    "finance":     ["借钱","贷款","存款","储蓄","还债","月供","收入","理财","负债","信用卡"],
    "universal":   [],
}

SEED_LESSONS = [
    ("investment","investment","allin时倾向高估胜率低估全输后果","可得性启发","allin前查历史同类决策胜率分布强制问最坏情况能否承受"),
    ("investment","investment","焦虑时低估黑天鹅风险高估收益","杏仁核劫持","焦虑时强制等待24小时让杏仁核平息后再评估"),
    ("investment","investment","买房时只收集支持买的理由忽视反对证据","确认偏误","买房前主动收集反对理由：历史下跌幅度租金回报率空置率"),
    ("investment","investment","小仓位试错比全押更安全","凸性结构","不确定时先小仓位验证假设等趋势确认再加仓"),
    ("investment","investment","牛市时过度自信觉得自己比大多数人强","乐观偏差自我归因","记录每次决策理由事后对比打破自我归因循环"),
    ("investment","investment","FOMO驱动决策看到别人赚钱就着急入场","损失厌恶","FOMO时强制等3天问自己是否研究过而非只看别人赚钱"),
    ("investment","investment","亏损后急于扳本加大赌注","风险追逐","亏损后等1周再决定不在情绪最强烈时操作账户"),
    ("investment","investment","allin后胜出通常因为有信息优势或风险预案","幸存者偏差","下次allin前确认相比上次是否真有更多信息优势"),
    ("investment","investment","不止盈只补仓越跌越买直到子弹打完","成本锚定","设硬止损线跌X%无条件减仓不找理由"),
    ("investment","investment","卖出盈利保留亏损","前景理论","定期平衡持仓强制卖出涨得多的不让情感干扰配置"),
    ("investment","investment","看专家推荐热点新闻后才做投资决策","权威偏差","投资前问自己是否独立研究过专家动机是什么"),
    ("investment","investment","单一事件后过度反应高估再次发生概率","赌徒谬误","每次重大事件后记录解读是否被短期波动打脸"),
    ("career","career","辞职时低估沉没成本失败概率和适应期压力","损失厌恶","辞职前计算6个月无收入失败概率家庭财务承受阈值"),
    ("career","career","跳槽时只看到新机会忽视旧积累和迁移成本","新鲜感偏差","跳槽前列出现公司未来1-2年成长路径和资源"),
    ("career","career","焦虑时高估新工作吸引力低估适应期难度","投射偏差","焦虑跳槽时等7天冷静期约谈目标公司在职员工后再决定"),
    ("career","career","裸辞后才发现休息比想象中压力大得多","享乐适应","裸辞前先请假2周模拟确认自己真的需要休息而非逃避"),
    ("career","career","接受offer时只谈薪资忽视发展机会和团队质量","聚焦效应","每次接受前问三年后这个职位值多少钱"),
    ("career","career","副业自由职业胜出因为有强执行力和财务缓冲","幸存者偏差","自由职业前先兼职试跑6个月确认收入可持续"),
    ("career","career","把忙碌当成生产力陷入低效加班循环","行动偏见","每周问一次这周最有价值的1件事是什么"),
    ("career","career","大龄求职时高估经验优势低估年龄歧视","内群体偏见","大龄求职准备可量化的业绩证据不只依赖工作年限"),
    ("relationship","relationship","情绪激动时做关系重大决策","情绪决策","重大关系决策等2周冷静期让情绪消退后再评估"),
    ("relationship","relationship","对方对你好时过度投入","投射理想化","记录每次对方没有满足期望的情况建立更客观的期待基线"),
    ("relationship","relationship","远距离冲突期通过频繁聊天维持感情错觉","互动密度错觉","定期问这段关系是否让彼此更好还是消耗精力"),
    ("relationship","relationship","闪婚后才发现价值观冲突不可调和","承诺升级","重大承诺前至少经历一次重大冲突来验证处理方式"),
    ("relationship","relationship","分手后马上找新欢用新关系逃避悲伤","反弹效应","分手后给自己至少6个月独处期再进入新关系"),
    ("relationship","relationship","婆媳冲突时无条件站父母忽视配偶感受","孝道文化","冲突时先和配偶统一立场再温和地和父母沟通"),
    ("family","family","为父母孩子做重大牺牲后积累怨恨","隐性契约","重大牺牲前明确表达自己的需求不假设对方知道"),
    ("family","family","在父母权威下压抑自己的真实需求","依恋类型","列出一直为父母做但内心不愿意的事评估是否可以设边界"),
    ("family","family","孩子教育时把自己的遗憾投射为孩子的目标","投射偏差","孩子的教育目标应以孩子兴趣为主而非父母的遗憾"),
    ("family","family","大家庭聚会后感到空虚或烦躁不知道为什么","情绪感染","每次大家庭聚会后记录真实感受逐步设立边界"),
    ("migration","migration","移民迁徙后低估文化适应期高估语言和融入速度","规划谬误","去之前和已在当地5年以上的华人深入交流不只看新移民的故事"),
    ("migration","migration","因短期情绪冲动决定回国或离开","状态依赖","情绪最低迷时不做永久性决定记录情绪周期再评估"),
    ("migration","migration","迁移后才发现当地华人圈子和想象中完全不同","可得性偏差","迁移前加入当地多类型社群了解不同群体的真实生活"),
    ("health","health","身体警告信号时拖延不就医","乐观偏差","同一症状3次以上就约医生不等自然好"),
    ("health","health","体检指标异常时不改变生活习惯觉得没症状就没事","可得性启发","建立健康追踪记录异常指标的数值变化趋势"),
    ("health","health","治疗方案只听一个医生就做决定","锚定偏差","慢性病或重大治疗前至少问两个医院的专业意见"),
    ("health","health","压力焦虑导致用吃喝酒刷手机麻痹自己","情绪调节失败","识别压力信号用运动替代逃避"),
    ("health","health","用健身强迫自己忽视身体过度疲劳信号","认知失调","倾听身体疲劳时强制休息不用意志力对抗身体信号"),
    ("health","health","长期久坐不运动觉得年轻不需要担心","时间折扣","每坐1小时站起来5分钟比偶尔高强度运动更有效"),
    ("education","education","读研读博时低估毕业难度高估就业溢价","信号理论","访谈5个该专业近3年毕业生了解真实就业收入"),
    ("education","education","考证学技能时追求数量不追求深度","确认仪式","每学新技能用项目证明掌握程度而非证书数量"),
    ("education","education","觉得读完这本书课程就会了","能力错觉","学完后立即教给别人或做实际项目检验"),
    ("finance","finance","借钱贷款时低估还款压力和意外概率","现金偏见","借款前计算真实月还款额问失业6个月还能还吗"),
    ("finance","finance","没有紧急备用金先享受再说","时间折扣","紧急备用金到位前禁止非必要借贷"),
    ("finance","finance","消费时用便宜合理化不需要的购买","价格锚定","买之前问这笔钱存1年后会值多少"),
    ("finance","finance","记账但从不分析","行为仪式","每月分析TOP3消费是什么哪项可以优化"),
    ("universal","universal","自我报告偏好与实际行为不一致","态度行为鸿沟","判断说自己会做某事时回顾兑现率"),
    ("universal","universal","近因效应：最近情绪经历强烈影响判断","序列位置效应","重要决策等24小时情绪消退后评估"),
    ("universal","universal","事后聪明偏差：结果倒推决策质量","结果偏见","分析决策过程而非结果本身本身本身本身本身"),
]


def _conn():
    return sqlite3.connect(str(_DB))

def _effective_confidence(row):
    stored = row.get("confidence", _DEFAULT_CONFIDENCE)
    if stored <= _MIN_CONFIDENCE: return stored
    lr = row.get("last_reinforced") or row.get("created_at")
    if not lr: return stored
    try:
        days = (datetime.now() - datetime.fromisoformat(lr)).total_seconds() / 86400
    except: return stored
    return max(math.exp(-_DECAY_RATE * days) * stored, _MIN_CONFIDENCE)

def _ensure_table():
    with _conn() as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type=? AND name=?", ("table","lessons"))
        if not cur.fetchone():
            for stmt in LESSONS_SCHEMA.strip().split(";"):
                s = stmt.strip()
                if s: c.execute(s)
            c.commit()
        cur2 = c.execute("SELECT COUNT(*) FROM lessons")
        if cur2.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            for lt,dom,pat,root,corr in SEED_LESSONS:
                c.execute("INSERT OR IGNORE INTO lessons (lesson_type,domain,pattern,root_cause,correction,created_at) VALUES (?,?,?,?,?,?)",(lt,dom,pat,root,corr,now))
            c.commit()

def _classify(text):
    text_lower = text.lower()
    scores = {}
    for domain, kws in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in kws if kw in text_lower)
    return sorted(scores.items(), key=lambda x: -x[1])[:3]

def init():
    _ensure_table()

def get_lessons(domain=None, min_confidence=0.15, limit=10):
    init()
    with _conn() as c:
        if domain:
            rows = c.execute("SELECT * FROM lessons WHERE domain=? AND confidence>=? ORDER BY confidence DESC LIMIT ?",(domain,min_confidence,limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM lessons WHERE confidence>=? ORDER BY confidence DESC LIMIT ?",(min_confidence,limit)).fetchall()
        result = []
        for r in rows:
            row = dict(zip(_LESSON_COLS, r))
            row["effective_confidence"] = _effective_confidence(row)
            result.append(row)
        return result

def update_confidence(lesson_id, outcome_score=1.0):
    init()
    with _conn() as c:
        cur = c.execute("SELECT confidence,times_applied FROM lessons WHERE id=?",(lesson_id,))
        row = cur.fetchone()
        if not row: return
        old_conf, times = row
        delta = (1.0-old_conf)*0.1 if outcome_score>=0.5 else -old_conf*0.1
        new_conf = max(_MIN_CONFIDENCE, min(1.0, old_conf+delta))
        now = datetime.now().isoformat()
        c.execute("UPDATE lessons SET confidence=?, last_reinforced=?, times_applied=? WHERE id=?",(new_conf,now,times+1,lesson_id))
        c.commit()

def lessons_to_prompt(task_text="", domain=None, limit=5):
    if not task_text: return ""
    init()
    doms = [domain] if domain else [d for d,_ in _classify(task_text)[:2]]
    if not doms: doms = ["universal"]
    lessons = []
    for d in doms: lessons.extend(get_lessons(domain=d, limit=limit))
    seen = set(); unique = []
    for L in lessons:
        k = L["pattern"][:20]
        if k not in seen: seen.add(k); unique.append(L)
    if not unique: return ""
    lines = ["[LESSONS] 相关教训（供参考）："]
    for L in unique[:limit]:
        ec = L["effective_confidence"]
        tag = "高" if ec>=0.7 else "中" if ec>=0.4 else "低"
        lt = L["lesson_type"]; pat = L["pattern"]; root = L["root_cause"]; corr = L["correction"]
        lines.append("  - ["+tag+"可信:"+lt+"] "+pat)
        lines.append("    根因: "+root)
        lines.append("    应对: "+corr)
    return "\n".join(lines)

def _llm_extract_lessons(text, chain_id=""):
    js_ex = '[{"lesson_type":"...","domain":"...","pattern":"...","root_cause":"...","correction":"..."}]'
    prompt = "你是一个决策行为分析专家。从以下文本中提取1-3个因果教训。lesson_type可选:warning/causal/pattern/antifragile/bias。输出JSON格式如：" + js_ex + "。如无教训输出[]。\n文本：\n"+text[:800]
    try:
        from adapters.llm import get_adapter
        resp = get_adapter().complete([{"role":"user","content":prompt}],
                                      model=None, temperature=0.3, max_tokens=500)
        content = resp.get("content","") if isinstance(resp,dict) else str(resp)
        m = re.search(r"\[(.*)\]", content, re.DOTALL)
        if m:
            import json as _js
            return _js.loads("["+m.group(1)+"]")
    except: pass
    # Fallback
    results = []
    for pat_re, lt, hint in _AUTO_EXTRACT_RULES:
        if re.search(pat_re, text):
            doms = [d for d,_ in _classify(text) if _>0]
            results.append({"lesson_type":lt,"domain":doms[0] if doms else "universal",
                           "pattern":hint,"root_cause":"规则提取","correction":"见教训"})
    return results

def save_lesson(lesson_type, domain, pattern, root_cause, correction, source="llm"):
    init()
    with _conn() as c:
        cur = c.execute("SELECT id,confidence FROM lessons WHERE pattern=? AND domain=?",(pattern,domain))
        row = cur.fetchone()
        now = datetime.now().isoformat()
        if row:
            cid, conf = row
            c.execute("UPDATE lessons SET confidence=?,last_reinforced=?,root_cause=?,correction=? WHERE id=?",(min(1.0,conf+0.05),now,root_cause,correction,cid))
            c.commit(); return cid
        else:
            cur = c.execute("INSERT INTO lessons (lesson_type,domain,pattern,root_cause,correction,source,created_at) VALUES (?,?,?,?,?,?,?)",(lesson_type,domain,pattern,root_cause,correction,source,now))
            c.commit(); return cur.lastrowid

def extract_and_save_from_case(chain_id, task_text, outcome_score=None, llm_raw=""):
    if not task_text: return []
    # [MiniMind Rep Penalty] 跳过高度重复的文本（无效教训来源）
    if is_repetitive(task_text, threshold=0.4):
        return []
    extracted = _llm_extract_lessons(task_text, chain_id=chain_id)
    saved_ids = []
    for ex in extracted:
        lid = save_lesson(ex.get("lesson_type","pattern"), ex.get("domain","universal"),
                         ex.get("pattern",""), ex.get("root_cause",""), ex.get("correction",""), "llm_extract")
        if outcome_score is not None and lid:
            update_confidence(lid, outcome_score)
        saved_ids.append(lid)
    if chain_id:
        with _conn() as c:
            cur = c.execute("SELECT name FROM sqlite_master WHERE type=? AND name=?",("table","lesson_extract_log"))
            if not cur.fetchone():
                c.execute("CREATE TABLE IF NOT EXISTS lesson_extract_log (id INTEGER PRIMARY KEY,chain_id TEXT,lesson_type TEXT,domain TEXT,pattern TEXT,root_cause TEXT,correction TEXT,llm_raw TEXT,created_at TEXT)")
                c.commit()
            now = datetime.now().isoformat()
            for ex in extracted:
                c.execute("INSERT INTO lesson_extract_log (chain_id,lesson_type,domain,pattern,root_cause,correction,llm_raw,created_at) VALUES (?,?,?,?,?,?,?,?)",(chain_id,ex.get("lesson_type"),ex.get("domain"),ex.get("pattern"),ex.get("root_cause"),ex.get("correction"),llm_raw,now))
            c.commit()
    return saved_ids

def classify_task_domain(task_text):
    if not task_text: return []
    return [(d,s) for d,s in _classify(task_text) if s>0] or [("universal",0)]

def get_lesson_stats():
    init()
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        avg_conf = c.execute("SELECT AVG(confidence) FROM lessons").fetchone()[0] or 0
        by_domain = {}
        for row in c.execute("SELECT domain, COUNT(*), AVG(confidence) FROM lessons GROUP BY domain").fetchall():
            by_domain[row[0]] = {"count":row[1],"avg_confidence":round(row[2],3) if row[2] else 0}
        by_type = {}
        for row in c.execute("SELECT lesson_type, COUNT(*) FROM lessons GROUP BY lesson_type").fetchall():
            by_type[row[0]] = row[1]
        verified = c.execute("SELECT COUNT(*) FROM lessons WHERE verified=1").fetchone()[0]
    return {"total":total,"avg_confidence":round(avg_conf,3),"by_domain":by_domain,"by_type":by_type,"verified":verified}

def print_lessons(domain=None, limit=10):
    lessons = get_lessons(domain=domain, limit=limit)
    if not lessons: print("(no lessons)"); return
    for L in lessons:
        ec = L["effective_confidence"]
        bar = "".join("X" if i<int(ec*10) else "." for i in range(10))
        print("["+str(L["id"])+"] "+L["domain"]+"/"+L["lesson_type"]+" "+bar+":"+str(round(ec,2)))
        print("     PATTERN: "+L["pattern"])
        print("     ROOT:    "+L["root_cause"])
        print("     CORR:    "+L["correction"])
        print()

if __name__ == "__main__":
    import sys, json
    args = sys.argv[1:]
    if args and args[0] in ("stats","list","show"):
        dom = args[1] if len(args)>1 else None
        if args[0]=="stats":
            print(json.dumps(get_lesson_stats(), indent=2, ensure_ascii=False))
        else:
            print_lessons(domain=dom)
    else:
        init()
        print("Lessons initialized: "+str(get_lesson_stats()["total"])+" seeds")
