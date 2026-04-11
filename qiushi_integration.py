"""
qiushi_integration.py — 实事求是方法论集成（qiushi-skill）

核心方法：
1. 矛盾分析：抓住主要矛盾，区分主次矛盾，矛盾相互转化
2. 调查研究：一切从实际出发，没有调查就没有发言权
3. 实践认识：实践→认识→再实践→再认识的循环
4. 群众路线：从群众中来，到群众中去
5. 批评与自我批评：自我净化，主动纠偏
6. 持久战略：战略上持久战，战术上歼灭战
7. 集中兵力：集中优势兵力，各个歼灭敌人
8. 星火燎原：星星之火，可以燎原，尊重萌芽力量
9. 统筹兼顾：统筹兼顾全局，照顾各方利益

用法：
    from qiushi_integration import quick_qiushi_check
    result = quick_qiushi_check("判断内容")
    print(qiushi_report(result))
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class QiushiCheck:
    """实事求是检查结果"""
    method: str  # 用到的方法论
    question: str  # 检查问题
    passed: Optional[bool]  # 是否通过/未通过（None=需要用户回答）
    suggestion: str  # 建议


# 每个维度对应 qiushi 方法论
QIUSHI_CHECKLIST = [
    {
        "method": "矛盾分析",
        "questions": [
            "当前最主要的矛盾是什么？你抓住了吗？",
            "主要矛盾和次要矛盾有没有转化可能？",
            "矛盾双方对立统一关系清晰吗？",
        ]
    },
    {
        "method": "调查研究",
        "questions": [
            "你掌握了第一手材料吗？还是只靠二手信息？",
            "关键事实核实了吗？有没有关键信息缺失？",
            "这个判断是基于事实还是基于概括/愿望/恐惧？",
        ]
    },
    {
        "method": "实践认识",
        "questions": [
            "这个判断可以通过小步实践验证吗？",
            "当前是认识阶段还是实践阶段？",
            "有反馈机制可以循环迭代吗？",
        ]
    },
    {
        "method": "群众路线",
        "questions": [
            "利益相关方的诉求都收集到了吗？",
            "你的判断是否忽略了某些群体的利益？",
            "结论反馈给利益相关方了吗？他们同意吗？",
        ]
    },
    {
        "method": "批评与自我批评",
        "questions": [
            "你主动找过自己判断的漏洞吗？",
            "接受别人的批评了吗？有没有偏见抗拒？",
            "错了会改吗？改的机制是什么？",
        ]
    },
    {
        "method": "持久战略",
        "questions": [
            "这个问题是速决战还是持久战？",
            "你有没有低估问题的长期性复杂性？",
            "心态和资源准备打持久战了吗？",
        ]
    },
    {
        "method": "集中兵力",
        "questions": [
            "当前最关键的点是什么？资源集中在这吗？",
            "有没有分散资源在次要问题上？",
            "可以集中优势兵力各个歼灭吗？",
        ]
    },
    {
        "method": "星火燎原",
        "questions": [
            "有没有新生萌芽力量被你低估了？",
            "小的胜利能不能积累成大的胜利？",
            "你是不是被当前劣势吓住了？",
        ]
    },
    {
        "method": "统筹兼顾",
        "questions": [
            "你考虑了全局吗？有没有只顾一头？",
            "长远利益和当前利益兼顾了吗？",
            "各方利益平衡了吗？",
        ]
    },
]


def quick_qiushi_check(task_text: str) -> List[QiushiCheck]:
    """
    快速求是检查：基于任务文本生成检查清单
    """
    results = []

    # 根据关键词匹配应该用什么方法
    # 匹配触发
    trigger_map = {
        "复杂": ["矛盾分析", "统筹兼顾"],
        "矛盾": ["矛盾分析"],
        "信息": ["调查研究"],
        "事实": ["调查研究"],
        "实践": ["实践认识"],
        "试试": ["实践认识"],
        "大家": ["群众路线"],
        "别人": ["群众路线"],
        "批评": ["批评与自我批评"],
        "错了": ["批评与自我批评"],
        "长期": ["持久战略"],
        "慢慢": ["持久战略"],
        "重点": ["集中兵力"],
        "关键": ["集中兵力"],
        "开始": ["星火燎原"],
        "机会": ["星火燎原"],
        "全局": ["统筹兼顾"],
        "兼顾": ["统筹兼顾"],
    }

    matched_methods = set()
    for keyword, methods in trigger_map.items():
        if keyword in task_text:
            for m in methods:
                matched_methods.add(m)

    # 如果没有匹配，默认走全套基础
    if not matched_methods:
        matched_methods = {"矛盾分析", "调查"}

    # 生成检查
    for checklist in QIUSHI_CHECKLIST:
        method = checklist["method"]
        # 如果方法名不匹配关键词，也保留一个核心问题
        if method not in matched_methods and len(matched_methods) >= 2:
            continue

        for q in checklist["questions"]:
            results.append(QiushiCheck(
                method=method,
                question=q,
                passed=None,  # 需要用户回答
                suggestion=f"请回答这个问题，帮助实事求是判断",
            ))

    return results


def format_qiushi_report(results: List[QiushiCheck]) -> str:
    """格式化求是检查报告"""
    from collections import defaultdict
    by_method = defaultdict(list)
    for r in results:
        by_method[r.method].append(r)

    lines = ["=== 实事求是求是检查报告 ===", ""]

    for method, checks in by_method.items():
        lines.append(f"【{method}】")
        for c in checks:
            lines.append(f"  ❓ {c.question}")
            if c.passed is not None:
                mark = "✅" if c.passed else "⚠️"
                lines[-1] += f" {mark} {c.suggestion}"
        lines.append("")

    lines.append("提示：实事求是是所有判断的总准绳，不能跳过。")
    return "\n".join(lines)
