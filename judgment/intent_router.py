# -*- coding: utf-8 -*-
import re, time
from collections import OrderedDict
from enum import Enum
from typing import Optional, Dict, Any, List

class IntentType(Enum):
    STATUS_QUERY   = "status_query"
    SHORT_ANSWER   = "short_answer"
    CONFIRM        = "confirm"
    COMMAND        = "command"
    CAREER_JUDGE   = "career_judge"
    INVEST_JUDGE   = "invest_judge"
    RELATION_JUDGE = "relation_judge"
    LIFE_OS_JUDGE  = "life_os_judge"
    COMPLEX_JUDGE  = "complex_judge"
    UNKNOWN        = "unknown"


class IntentMatch:
    def __init__(self, type_: IntentType, keywords: List[str],
                 min_len: int = 0, max_len: int = 999,
                 exclude: List[str] = None, score: int = 1):
        self.type = type_
        self.keywords = keywords
        self.min_len = min_len
        self.max_len = max_len
        self.exclude = exclude or []
        self.score = score
        self._regexes = []
        for kw in keywords:
            parts = kw.split()
            if len(parts) > 1:
                escaped = r"\s+".join(re.escape(p) for p in parts)
            else:
                escaped = re.escape(kw)
            self._regexes.append(re.compile(escaped, re.IGNORECASE))

    def match(self, text: str) -> bool:
        if len(text) < self.min_len or len(text) > self.max_len:
            return False
        for kw_re in self._regexes:
            if kw_re.search(text):
                for ex in self.exclude:
                    if ex.lower() in text.lower():
                        return False
                return True
        return False


class IntentRouter:
    def __init__(self):
        self._rules: List[IntentMatch] = []
        self._cache: OrderedDict = OrderedDict()
        self._cache_max = 200
        self._last_clear = time.time()
        self._build_rules()

    def _build_rules(self):
        # ── 优先级1：具体领域（必须最前，否则被通用规则抢走） ──

        # 职业决策
        self._rules.append(IntentMatch(
            IntentType.CAREER_JUDGE,
            ["跳槽", "辞职", "读研", "考研", "考公", "移民",
             "换工作", "offer", "要不要去", "要不要换",
             "要不要接受", "要不要离开", "工作选择"],
            min_len=3, max_len=200,
        ))

        # 投资决策（排除"是不是"确认句）
        self._rules.append(IntentMatch(
            IntentType.INVEST_JUDGE,
            ["all in", "全仓", "炒股", "股票", "基金", "买房",
             "借钱投资", "贷款", "要不要买房", "要不要创业",
             "数字货币", "虚拟货币", "抄底", "要不要抄底"],
            min_len=3, max_len=200,
            exclude=["是不是", "该不该"],
        ))

        # 人际关系
        self._rules.append(IntentMatch(
            IntentType.RELATION_JUDGE,
            ["吵架", "矛盾", "冲突", "分手", "挽回",
             "怎么处理关系", "领导", "同事关系",
             "朋友关系", "夫妻", "男/女朋友", "喜欢我"],
            min_len=3, max_len=200,
        ))

        # 生活调度
        self._rules.append(IntentMatch(
            IntentType.LIFE_OS_JUDGE,
            ["今天做什么", "精力", "状态不好", "想休息",
             "工作安排", "怎么分配时间", "效率低", "拖延",
             "早起了", "熬夜", "健身", "运动", "休息",
             "睡眠", "焦虑", "压力大", "时间管理"],
            min_len=2, max_len=60,
        ))

        # ── 优先级2：指令类 ──
        self._rules.append(IntentMatch(
            IntentType.COMMAND,
            ["帮我", "帮我做", "请帮我", "执行", "做一下",
             "生成", "创建", "写一个", "帮我写"],
            min_len=2, max_len=60,
        ))

        # ── 优先级3：确认类 ──
        self._rules.append(IntentMatch(
            IntentType.CONFIRM,
            ["是不是对的", "对不对", "是不是应该", "是不是好",
             "好不好", "是不是真的", "是不是在", "能不能",
             "行不行", "是不是喜欢我", "是不是喜欢",
             "要还是不要", "是不是", "该不该"],
            min_len=2, max_len=50,
        ))

        # ── 优先级4：状态查询 ──
        self._rules.append(IntentMatch(
            IntentType.STATUS_QUERY,
            ["状态", "情况怎么样", "现在怎样", "最近如何",
             "判断状态", "看看", "检查"],
            min_len=2, max_len=30,
        ))

    def route(self, text: str) -> IntentType:
        text = text.strip()
        if not text:
            return IntentType.UNKNOWN
        now = time.time()
        if now - self._last_clear > 60:
            self._cache.clear()
            self._last_clear = now
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        for rule in self._rules:
            if rule.match(text):
                intent = rule.type
                self._cache_to(intent, text)
                return intent
        intent = self._infer_complexity(text)
        self._cache_to(intent, text)
        return intent

    def _infer_complexity(self, text: str) -> IntentType:
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        sentences = len(re.split(r'[。！？.!?]+', text))
        if sentences >= 2 and chinese_chars >= 20:
            return IntentType.COMPLEX_JUDGE
        if chinese_chars <= 15:
            question_kw = ["是什么", "为什么", "怎么办", "怎么看",
                           "如何", "哪个好", "是不是", "要不要"]
            for kw in question_kw:
                if kw in text:
                    return IntentType.SHORT_ANSWER
            return IntentType.COMPLEX_JUDGE
        return IntentType.COMPLEX_JUDGE

    def _cache_to(self, intent: IntentType, text: str):
        if text in self._cache:
            self._cache.move_to_end(text)
        else:
            if len(self._cache) >= self._cache_max:
                self._cache.popitem(last=False)
        self._cache[text] = intent

    # ── P0: 工具路由（everything-copilot-cli "model choice = routing" 模式）────
    TOOL_ROUTES = [
        # claude_code: 代码/重构/实现类
        (["代码", "写代码", "implement", "bug", "fix bug", "refactor",
          "重构", "review code", "代码审查", "write code",
          "帮我写", "create function", "函数", "class ", "算法"],
         "claude_code"),
        # hermes: 调研/搜索/研究类
        (["调研", "搜索", "research", "调查", "查一下",
          "了解一下", "告诉我关于", "帮我查"],
         "hermes"),
        # codex: 快速代码生成/补全（codex CLI 安装后启用）
        (["补全", "complete", "autocomplete", "snippet", "模板代码",
          "generate code"],
         "codex"),
    ]

    def tool_route(self, text: str) -> tuple:
        """
        返回 (tool_name, task_text) 或 None。
        基于 everything-copilot-cli "model choice = routing" 模式：
        - 模型选择是路由决策，不是固定分配
        - 不同任务类型路由到最适合的工具
        """
        text_lower = text.lower()
        for keywords, tool in self.TOOL_ROUTES:
            for kw in keywords:
                if kw.lower() in text_lower:
                    return (tool, text)
        return None

    def explain(self, text: str) -> Dict[str, Any]:
        intent = self.route(text)
        reason = self._get_intent_reason(intent, text)
        should_skip_llm = intent in (
            IntentType.STATUS_QUERY, IntentType.SHORT_ANSWER, IntentType.CONFIRM
        )
        # P0: 工具路由（everything-copilot-cli "model choice = routing"）
        tool_info = self.tool_route(text)
        return {
            "intent": intent.value,
            "reason": reason,
            "skip_llm": should_skip_llm,
            "skip_check10d": should_skip_llm,
            "suggested_action": self._get_action(intent),
            "tool_route": tool_info[0] if tool_info else None,  # 路由到哪个工具
            "tool_task": tool_info[1] if tool_info else None,
            "tool_action": self.get_tool_action(tool_info[0]) if tool_info else None,
            "routing_source": "everything-copilot-cli:model-choice-as-routing",
        }

    def _get_intent_reason(self, intent: IntentType, text: str) -> str:
        reasons = {
            IntentType.STATUS_QUERY: "命中状态查询关键词",
            IntentType.CONFIRM: "命中确认类关键词（是不是/要不要/该不该）",
            IntentType.COMMAND: "命中指令关键词（帮我/做/生成）",
            IntentType.LIFE_OS_JUDGE: "命中精力/时间管理关键词",
            IntentType.INVEST_JUDGE: "命中投资决策关键词",
            IntentType.CAREER_JUDGE: "命中职业决策关键词",
            IntentType.RELATION_JUDGE: "命中人际关系关键词",
            IntentType.SHORT_ANSWER: "短文本，简单问答",
            IntentType.COMPLEX_JUDGE: "复杂文本，需要完整10维判断",
            IntentType.UNKNOWN: "无法识别，默认完整判断",
        }
        return reasons.get(intent, "未知原因")
    def _get_action(self, intent: IntentType) -> str:
        actions = {
            IntentType.STATUS_QUERY: "直接返回状态（无需判断）",
            IntentType.CONFIRM: "轻量级 yes/no 判断（可缓存）",
            IntentType.COMMAND: "执行工具/CLI，不进判断",
            IntentType.LIFE_OS_JUDGE: "调用 life_os.py",
            IntentType.INVEST_JUDGE: "check10d_run（投资场景）",
            IntentType.CAREER_JUDGE: "check10d_run（职业场景）",
            IntentType.RELATION_JUDGE: "check10d_run（关系场景）",
            IntentType.SHORT_ANSWER: "直接回答（无判断）",
            IntentType.COMPLEX_JUDGE: "check10d_run（完整）",
            IntentType.UNKNOWN: "check10d_run（默认）",
        }
        return actions.get(intent, "check10d_run（默认）")

    def get_tool_action(self, tool: str) -> str:
        """P0: 工具路由动作映射（everything-copilot-cli 模式）"""
        tool_actions = {
            "claude_code": "copaw agents chat --to claude --message <task>",
            "hermes": "copaw agents chat --to hermes --message <task>",
            "codex": "codex <task> (Codex CLI, 安装后启用)",
        }
        return tool_actions.get(tool, f"未知工具: {tool}")

    def stats(self) -> Dict[str, Any]:
        return {"cache_size": len(self._cache), "cache_max": self._cache_max,
                "rules_count": len(self._rules)}


_router_instance: Optional[IntentRouter] = None

def get_router() -> IntentRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = IntentRouter()
    return _router_instance


def route_input(text: str) -> IntentType:
    return get_router().route(text)


def should_skip_judgment(text: str) -> bool:
    intent = route_input(text)
    return intent in (
        IntentType.STATUS_QUERY, IntentType.SHORT_ANSWER,
        IntentType.CONFIRM, IntentType.COMMAND,
    )


if __name__ == "__main__":
    router = get_router()
    test_cases = [
        ("状态怎么样", IntentType.STATUS_QUERY),
        ("要不要辞职创业", IntentType.CAREER_JUDGE),
        ("要不要 all in 炒股", IntentType.INVEST_JUDGE),
        ("今天做什么好", IntentType.LIFE_OS_JUDGE),
        ("是不是应该买房", IntentType.CONFIRM),
        ("怎么看待这件事", IntentType.SHORT_ANSWER),
        ("帮我生成一份报告", IntentType.COMMAND),
        ("和朋友吵架了怎么办", IntentType.RELATION_JUDGE),
        ("她是不是喜欢我", IntentType.RELATION_JUDGE),
        ("要还是不要", IntentType.CONFIRM),
        ("人生好迷茫啊", IntentType.COMPLEX_JUDGE),
        ("我35岁程序员深圳有两套房要all in炒股吗", IntentType.INVEST_JUDGE),
    ]
    print("=== IntentRouter 测试 ===")
    all_pass = True
    for text, expected in test_cases:
        got = router.route(text)
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            all_pass = False
        print(f"[{status}] [{got.value}] {text!r}")
    print()
    print(f"统计: {router.stats()}")
    print("结果:", "全部通过" if all_pass else "有失败")
