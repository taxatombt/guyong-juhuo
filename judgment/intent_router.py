"""ZeusHammer LocalBrain IntentRouter - ZeusHammer LocalBrain IntentRouter"""
from __future__ import annotations
from collections import OrderedDict
from enum import Enum
from typing import Optional, Dict, Any
class IntentType(Enum):
    STATUS_QUERY="status_query";HELP_QUERY="help_query";KNOWLEDGE="knowledge"
    LIFE_OS="life_os";BIO_QUERY="bio_query";VERDICT_LIST="verdict_list"
    BEHAVIOR_Q="behavior_q";CONFIG_Q="config_q"
    CAREER_JUDGE="career";INVEST_JUDGE="invest";RELATION_JUDGE="relation"
    LIFE_JUDGE="life_judge";MONEY_JUDGE="money_judge";EDUCATION_J="education_j"
    HEALTH_J="health_j";FAMILY_J="family_j";UNKNOWN="unknown"
_P=[
(IntentType.STATUS_QUERY,["状态","怎么样","查看判断","判断记录","历史判断","verdict","维度信念","系统状态"],10),
(IntentType.HELP_QUERY,["怎么用","help","使用说明","命令","功能","帮忙","教我"],10),
(IntentType.KNOWLEDGE,["什么是","告诉我关于","介绍一下","解释","概念","定义"],10),
(IntentType.LIFE_OS,["今天做什么","精力","任务规划","本周计划","schedule","日程","todo","life os"],8),
(IntentType.BIO_QUERY,["我的背景","我是谁","用户画像","biography","我的情况","个人信息","生平"],8),
(IntentType.VERDICT_LIST,["判断列表","verdict list","查看历史","历史记录","judgments","判断历史"],8),
(IntentType.BEHAVIOR_Q,["行为记录","behavior","最近做了什么","agent行为"],8),
(IntentType.CONFIG_Q,["config","配置","设置","api key"],8),
(IntentType.CAREER_JUDGE,["辛职","跃汁","offer","工作选择","加班","晋升","辛职吗","跃汁吗","职业","裁员","面试","创业","副业","工资","年终奖"],6),
(IntentType.INVEST_JUDGE,["all in","allin","炸肤","投资","基金","全仓","加仓","减仓","理财","借钱炸肤","棲哈","技底","止损","股票"],6),
(IntentType.RELATION_JUDGE,["分手","离婚","复合","情感","情侶","婚姻","追求","表白","暗恋","第三者","出轨","争吼"],6),
(IntentType.LIFE_JUDGE,["买房","移民","买房吗","移民吗","定居","秛房","换城市","搬家","装修"],6),
(IntentType.MONEY_JUDGE,["借钱","负债","贷款","收入","存款","月供","年入","财务"],6),
(IntentType.EDUCATION_J,["读研","考研","留学","读研吗","考研吗","证业","学历","MBA","培训"],6),
(IntentType.HEALTH_J,["手术","健康","体检","病例","吃药","治疗","戒烟","戒酒"],6),
(IntentType.FAMILY_J,["结婚","生子","结婚吗","生子吗","生二胎","孩子教育","彩礼"],6),
(IntentType.UNKNOWN,[],5),
]
_DIRECT_MAP={"状态":IntentType.STATUS_QUERY,"verdict":IntentType.STATUS_QUERY,"verdict list":IntentType.VERDICT_LIST,"help":IntentType.HELP_QUERY,"all in":IntentType.INVEST_JUDGE,"allin":IntentType.INVEST_JUDGE,"棲哈":IntentType.INVEST_JUDGE,"辛职":IntentType.CAREER_JUDGE,"跃汁":IntentType.CAREER_JUDGE,"买房":IntentType.LIFE_JUDGE,"移民":IntentType.LIFE_JUDGE,"分手":IntentType.RELATION_JUDGE,"借钱":IntentType.MONEY_JUDGE,"读研":IntentType.EDUCATION_J}
_NO_CHECK10D={IntentType.STATUS_QUERY,IntentType.HELP_QUERY,IntentType.KNOWLEDGE,IntentType.LIFE_OS,IntentType.BIO_QUERY,IntentType.VERDICT_LIST,IntentType.BEHAVIOR_Q,IntentType.CONFIG_Q}

class _IntentCache:
    def __init__(self, max_size=100):
        self._c=OrderedDict(); self._max=max_size
    def get(self, k):
        if k in self._c: self._c.move_to_end(k); return self._c[k]
        return None
    def set(self, k, v):
        if k in self._c: self._c.move_to_end(k)
        elif len(self._c)>=self._max: self._c.popitem(last=False)
        self._c[k]=v
    def clear(self): self._c.clear()
    def __len__(self): return len(self._c)
class IntentResult:
    def __init__(self, it, chk, conf=0.0, kw="", note=""):
        self.intent_type=it; self.should_check10d=chk
        self.confidence=conf; self.matched_kw=kw; self.note=note
    def __repr__(self):
        return f"IntentResult({self.intent_type.value},check10d={self.should_check10d},conf={self.confidence:.2f})"
    def to_dict(self):
        return {"intent_type":self.intent_type.value,"should_check10d":self.should_check10d,"confidence":self.confidence,"matched_kw":self.matched_kw,"note":self.note}
class IntentRouter:
    _instance=None
    def __init__(self): self._cache=_IntentCache(100)
    @classmethod
    def get_instance(cls):
        if cls._instance is None: cls._instance=cls()
        return cls._instance
    def route(self, text):
        if not text or not text.strip():
            return IntentResult(IntentType.UNKNOWN,True,0.0,"","空输入")
        text=text.strip(); key=text[:80]
        cached=self._cache.get(key)
        if cached is not None:
            return IntentResult(cached,cached not in _NO_CHECK10D,1.0,"","[缓存]")
        it,conf,kw=self._classify(text)
        self._cache.set(key,it)
        return IntentResult(it,it not in _NO_CHECK10D,conf,kw,"")
    def _classify(self, text):
        if len(text)<=10:
            # Longest match first to avoid "verdict" matching before "verdict list"
            for k,v in sorted(_DIRECT_MAP.items(), key=lambda x:-len(x[0])):
                if k==text or text in k: return v,0.95,k
        best,bestc,bestk=IntentType.UNKNOWN,0.0,""
        # Sort all (intent, keyword) pairs by keyword length desc to prefer longer matches
        candidates=[]
        for it,kws,pri in _P:
            for kw in kws:
                if kw in text:
                    candidates.append((len(kw),kw,it,pri))
        # Longer keyword = higher priority, then higher pattern priority as tiebreaker
        candidates.sort(key=lambda x:(x[0],x[3]), reverse=True)
        if candidates:
            _,kw,it,pri=candidates[0]
            cov=len(kw)/max(len(text),1)
            conf=min(pri/10.0+cov,1.0)
            best,bestc,bestk=it,conf,kw
        return best,bestc,bestk
    def clear_cache(self): self._cache.clear()
    def cache_size(self): return len(self._cache)
def route(text): return IntentRouter.get_instance().route(text)

def direct_reply(it, text):
    if it == IntentType.STATUS_QUERY:
        try:
            from judgment.closed_loop import get_judgment_stats
            s = get_judgment_stats()
            return f"判断系统状态：共 {s.get('total',0)} 条判断，正确 {s.get('correct',0)} 条"
        except: return "判断系统运行正常"
    if it == IntentType.HELP_QUERY:
        return "用法：\n  python cli.py judge <问题> - 十维判断\n  python hub.py status - 查看状态\n  python hub.py verdict --show - 查看历史"
    if it == IntentType.KNOWLEDGE:
        kb = {
            "all in": "把所有资金投入单一标的，风险极高。建议先小仓位验证。",
            "止损": "止损是保护本金的重要手段。",
            "买房": "买房需考虑：首付、月供、工作稳定性、城市发展。",
            "辛职": "辛职前：储备 6-12 个月生活费。",
        }
        for k, v in kb.items():
            if k in text: return v
        return f"关于「{text[:20]}」的建议：用 juhuo 做十维判断获取个性化建议。"
    if it == IntentType.LIFE_OS:
        return "life_os用法：python life_os.py <任务1>/<任务2>/... --energy 80\n例：python life_os.py 写报告/健身/见客户"
    if it == IntentType.BIO_QUERY:
        try:
            from judgment.biography import get_context as bio_ctx
            ctx = bio_ctx()
            return ctx if ctx else "暂无用户背景记录。"
        except: return "暂无用户背景记录。"
    if it == IntentType.VERDICT_LIST:
        try:
            from judgment.closed_loop import get_judgment_stats
            s = get_judgment_stats()
            return f"历史判断：共{s.get('total',0)}条，准确率{s.get('accuracy','N/A')}"
        except: return "暂无历史判断记录。"
    if it == IntentType.BEHAVIOR_Q: return "行为记录：暂无。使用juhuo时自动记录行为轨迹。"
    if it == IntentType.CONFIG_Q: return "配置：用python hub.py config set <key> <value>查看/修改。"
    return ""
def handle(text):
    r = route(text)
    if r.should_check10d: return None
    return direct_reply(r.intent_type, text)
