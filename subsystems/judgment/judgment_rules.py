#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment_rules.py — Juhuo 十维推理规则引擎

P3改进: 给judgment添加self-contained推理规则
"""

import re
from typing import Dict, List
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class RuleResult:
    dimension: str
    passed: bool
    score: float
    reason: str
    needs_llm: bool
    details: Dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class BaseRule(ABC):
    dimension: str = ""
    
    @abstractmethod
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        pass
    
    def _s(self, passed: bool, conf: float = 0.8) -> float:
        return conf if passed else 1 - conf


class CognitiveRule(BaseRule):
    dimension = "cognitive"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        neg = len(re.findall(r"可能[吧嘛]|大概|也许|不清楚|搞不懂", task_text))
        pos = len(re.findall(r"因为.{0,20}(所以|因此)|经过分析|具体来说|综上所述", task_text))
        passed = pos > neg or "?" not in task_text
        return RuleResult(self.dimension, passed, min(1.0, max(0.0, 0.5+0.1*(pos-neg))),
                        f"逻辑: 正{pos} 负{neg}", abs(pos-neg) <= 1, {"pos": pos, "neg": neg})


class GameTheoryRule(BaseRule):
    dimension = "game_theory"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        players = len(re.findall(r"甲方|乙方|用户|客户|对手|竞争|合作|博弈", task_text))
        strategy = len(re.findall(r"策略|方案|选择|决策|谈判|筹码|底线", task_text))
        passed = players >= 2 and strategy >= 1
        return RuleResult(self.dimension, passed, min(1.0, (players/2+strategy)*0.3),
                        f"博弈: 参与{players}, 策略{strategy}", not passed,
                        {"players": players, "strategy": strategy})


class EconomicRule(BaseRule):
    dimension = "economic"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        cost = len(re.findall(r"成本|费用|花费|投入|消耗|损失|代价", task_text))
        benefit = len(re.findall(r"收益|利润|回报|盈利|价值|好处", task_text))
        roi = len(re.findall(r"值得|划算|回报率|性价比|ROI", task_text))
        has_econ = cost > 0 or benefit > 0
        passed = has_econ and (benefit >= cost or roi > 0)
        return RuleResult(self.dimension, passed, min(1.0, (cost+benefit+roi*2)*0.2),
                        f"经济: 成本{cost}, 收益{benefit}, ROI{roi}", not has_econ,
                        {"cost": cost, "benefit": benefit, "roi": roi})


class DialecticalRule(BaseRule):
    dimension = "dialectical"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        pros = len(re.findall(r"优点|优势|好处|利好|正面|有利|正确", task_text))
        cons = len(re.findall(r"缺点|劣势|坏处|风险|问题|负面|错误", task_text))
        both = len(re.findall(r"但是|然而|不过|同时|虽然", task_text))
        passed = (pros > 0 and cons > 0) or both >= 2
        return RuleResult(self.dimension, passed, min(1.0, (pros+cons+both)*0.2),
                        f"辩证: 正{pros}, 反{cons}, 转折{both}", not (pros > 0 and cons > 0),
                        {"pros": pros, "cons": cons, "both": both})


class EmotionalRule(BaseRule):
    dimension = "emotional"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        emotions = len(re.findall(r"焦虑|担心|害怕|愤怒|高兴|失落|压力|紧张", task_text))
        intense = len(re.findall(r"非常|特别|极其|十分|太|超", task_text))
        control = len(re.findall(r"控制|冷静|理性|客观|分析|思考", task_text))
        caution = emotions > 0 and intense > 0 and control == 0
        score = 0.9 if control > 0 else (0.5 if emotions > 0 else 0.8)
        return RuleResult(self.dimension, not caution, score,
                        f"情绪: 词{emotions}, 强度{intense}, 控制{control}", caution,
                        {"emotions": emotions, "intense": intense, "control": control})


class IntuitiveRule(BaseRule):
    dimension = "intuitive"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        gut = len(re.findall(r"直觉|第六感|感觉|猜测|估计", task_text))
        evidence = len(re.findall(r"数据|证据|事实|证明|依据|参考", task_text))
        passed = evidence >= gut
        return RuleResult(self.dimension, passed, min(1.0, evidence*0.3-gut*0.1+0.5),
                        f"直觉: 信号{gut}, 证据{evidence}", gut > 2 and evidence == 0,
                        {"gut": gut, "evidence": evidence})


class MoralRule(BaseRule):
    dimension = "moral"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        ethics = len(re.findall(r"道德|伦理|正义|公平|诚信|诚实|责任|应该", task_text))
        harm = len(re.findall(r"伤害|欺骗|隐瞒|作弊|剥削|不公平", task_text))
        passed = ethics > 0 and harm == 0
        return RuleResult(self.dimension, passed, min(1.0, (ethics-harm*2)*0.2+0.5),
                        f"道德: 伦理{ethics}, 伤害{harm}", harm > 0 and ethics == 0,
                        {"ethics": ethics, "harm": harm})


class SocialRule(BaseRule):
    dimension = "social"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        group = len(re.findall(r"大家|人们|社会|群体|团队|公司|组织|国家|公众", task_text))
        impact = len(re.findall(r"影响|作用|关系|合作|冲突|协调|沟通|共识", task_text))
        passed = group >= 1 or impact >= 2
        return RuleResult(self.dimension, passed, min(1.0, (group+impact)*0.3),
                        f"社会: 群体{group}, 影响{impact}", group == 0 and impact < 2,
                        {"group": group, "impact": impact})


class TemporalRule(BaseRule):
    dimension = "temporal"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        short = len(re.findall(r"现在|当前|短期|立即|马上|今天|近期|暂时", task_text))
        long = len(re.findall(r"长期|未来|以后|将来|持续|历史|过去|传统", task_text))
        both = short > 0 and long > 0
        passed = both or long >= 2
        return RuleResult(self.dimension, passed, min(1.0, (short+long*1.5)*0.3),
                        f"时间: 短期{short}, 长期{long}", not both and long == 0,
                        {"short": short, "long": long})


class MetacognitiveRule(BaseRule):
    dimension = "metacognitive"
    
    def evaluate(self, task_text: str, context: Dict = None) -> RuleResult:
        meta = len(re.findall(r"思考|反思|复盘|总结|判断|决策|认知|理解|学习", task_text))
        uncertainty = len(re.findall(r"不确定|未知|可能有|估计|大概|可能", task_text))
        passed = meta >= 2 and uncertainty <= 2
        return RuleResult(self.dimension, passed, min(1.0, meta*0.2-uncertainty*0.1+0.5),
                        f"元认知: 思考词{meta}, 不确定{uncertainty}", meta < 2,
                        {"meta": meta, "uncertainty": uncertainty})


# ── 规则引擎 ────────────────────────────────────────────────────────
_RULES = {
    "cognitive": CognitiveRule(),
    "game_theory": GameTheoryRule(),
    "economic": EconomicRule(),
    "dialectical": DialecticalRule(),
    "emotional": EmotionalRule(),
    "intuitive": IntuitiveRule(),
    "moral": MoralRule(),
    "social": SocialRule(),
    "temporal": TemporalRule(),
    "metacognitive": MetacognitiveRule(),
}


def evaluate_all_rules(task_text: str, context: Dict = None) -> Dict[str, RuleResult]:
    """评估所有维度规则"""
    return {dim: rule.evaluate(task_text, context) for dim, rule in _RULES.items()}


def get_llm_required_dimensions(task_text: str, context: Dict = None) -> List[str]:
    """获取需要LLM的维度列表"""
    results = evaluate_all_rules(task_text, context)
    return [dim for dim, r in results.items() if r.needs_llm]


def get_rule_scores(task_text: str, context: Dict = None) -> Dict[str, float]:
    """获取规则分数"""
    results = evaluate_all_rules(task_text, context)
    return {dim: r.score for dim, r in results.items()}


def rule_based_precheck(task_text: str, context: Dict = None) -> Dict:
    """规则预检: 快速判断任务是否需要详细LLM分析"""
    results = evaluate_all_rules(task_text, context)
    llm_dims = [dim for dim, r in results.items() if r.needs_llm]
    low_score_dims = [dim for dim, r in results.items() if r.score < 0.5]
    
    return {
        "needs_llm": len(llm_dims) > 0,
        "llm_dimensions": llm_dims,
        "rule_scores": {dim: r.score for dim, r in results.items()},
        "low_score_dimensions": low_score_dims,
        "all_passed": all(r.passed for r in results.values()),
        "details": {dim: {"reason": r.reason, "passed": r.passed} for dim, r in results.items()},
    }
