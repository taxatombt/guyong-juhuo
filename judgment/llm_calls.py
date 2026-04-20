#!/usr/bin/env python3
# judgment/llm_calls.py — LLM 调用函数（从 router.py 拆分）
# 
# 职责：
#   inject_emotion_signal — 情绪信号文本注入
#   _build_answer_prompt   — 构建 LLM prompt
#   _answer_questions      — 调用 LLM 回答维度问题
#   _keyword_match         — 关键词匹配工具
#   _synthesize_verdict    — verdict 合成 + 句子评分
#
# 测试：可直接 pytest mock _MOCK_ADAPTER，不依赖 router.py

from __future__ import annotations
import re
from typing import Dict, List, Optional

# 由 router.py 注入
global_emotion_system = None

# 测试用 mock adapter（pytest fixture 可覆盖）
_MOCK_ADAPTER = None


def inject_emotion_signal(task_text: str) -> str:
    """兼容旧接口：如果情绪信号需要重视，返回提示文本"""
    # 先检测情绪（我们只需要文本关键词检测，这里传入空判断结果）
    signal = global_emotion_system.detect_emotion(task_text, {})
    if signal.is_signal:
        return f"\n[情绪信号提示] {signal.description}\n"
    return None



def _build_answer_prompt(task_text: str, questions: dict, agent_profile: dict = None, prior_adj: dict = None, history_context: str = "") -> str:
    """构造LLM回答问题的prompt"""
    dim_labels = {
        "cognitive": "认知维度",
        "game_theory": "博弈维度",
        "economic": "经济维度",
        "dialectical": "辩证维度",
        "emotional": "情绪维度",
        "intuitive": "直觉维度",
        "moral": "道德维度",
        "social": "社会维度",
        "temporal": "时间维度",
        "metacognitive": "元认知维度",
    }

    profile_context = ""
    if agent_profile:
        name = agent_profile.get("name", "通用AI")
        profile_context = f"\n你是{name}的判断分身。价值取向：{', '.join(agent_profile.get('values', []))}。"

    parts = [
        f"任务：{task_text}{profile_context}\n",
        "请针对以下问题给出简短而深刻的回答（每条回答不超过50字）：\n",
    ]

    for dim_id, qs in questions.items():
        label = dim_labels.get(dim_id, dim_id)
        if not qs:
            continue
        parts.append(f"【{label}】")
        for i, q in enumerate(qs, 1):
            parts.append(f"  Q{i}. {q}")
        parts.append("")

    parts.append("【回答格式要求】")
    parts.append("每个维度末尾必须加一行 `=>` 开头的结论，例如：")
    parts.append("  => 认知建议：先评估技能市场价值再做决定")
    parts.append("所有维度回答完后，另起一行输出：")
    parts.append("## 最终结论：你的判断（10-20字，直接说行动，不说分析）")
    parts.append("例如：## 最终结论：建议先做市场调研再决定是否创业。")

    # 历史经历参考（如果有）
    if history_context:
        parts.insert(1, history_context)

    return "\n".join(parts)



def _answer_questions(task_text: str, questions: dict, agent_profile: dict = None, prior_adj: dict = None, history_context: str = "") -> dict:
    """调用MiniMax LLM回答所有维度问题，返回 {dim_id: answer_text, ...}"""
    adapter = get_adapter()

    # 如果没有配置api_key（环境变量也没有），返回空
    if not adapter.is_configured():
        print("[LLM] MiniMax未配置 api_key，跳过answer生成")
        return {}

    prompt = _build_answer_prompt(task_text, questions, agent_profile, prior_adj, history_context)

    # 截断prompt（LLM context limit）
    if len(prompt) > 6000:
        prompt = prompt[:6000] + "\n[内容过长已截断]"

    try:
        response = adapter.complete(CompletionRequest(
            prompt=prompt,
            max_tokens=2048,
            temperature=0.7,
        ))

        # ── InsightTracker: 记录 token 消耗 ─────────────────────────
        try:
            from judgment.insight_tracker import insight_tracker
            _t = insight_tracker()
            _t.record_input(response.usage_input if hasattr(response, 'usage_input') and response.usage_input else len(prompt) // 4)
            _t.record_output(response.usage_output if hasattr(response, 'usage_output') and response.usage_output else len(response.content) // 4)
            if hasattr(response, 'cost') and response.cost:
                _t.record_cost(response.cost)
        except Exception:
            pass

        if not response.success:
            print(f"[LLM] 调用失败: {response.error}")
            return {}

        # 简单按行解析：格式为 "【维度名】回答内容"
        answers = {}
        current_dim = None
        current_content = []

        dim_labels_inv = {
            "认知维度": "cognitive",
            "博弈维度": "game_theory",
            "经济维度": "economic",
            "辩证维度": "dialectical",
            "情绪维度": "emotional",
            "直觉维度": "intuitive",
            "道德维度": "moral",
            "社会维度": "social",
            "时间维度": "temporal",
            "元认知维度": "metacognitive",
        }

        for line in response.content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 检测维度标题行
            matched_dim = None
            for label, dim_id in dim_labels_inv.items():
                if label in line:
                    matched_dim = dim_id
                    break

            if matched_dim:
                # 保存上一维度的答案
                if current_dim and current_content:
                    answers[current_dim] = " ".join(current_content).strip()
                current_dim = matched_dim
                current_content = []
                # 去除标题，只保留后面的内容
                rest = line.split("】", 1)
                if len(rest) > 1:
                    content = rest[1].strip()
                    if content:
                        current_content.append(content)
            elif current_dim and line:
                # 普通内容行，拼接到当前维度
                current_content.append(line)

        # 保存最后一个维度
        if current_dim and current_content:
            answers[current_dim] = " ".join(current_content).strip()

        return answers

    except Exception as e:
        print(f"[LLM] 回答生成异常: {e}")
        return {}


# 维度优先级分类
# 优先级原则（聚活项目设计）：
# - game_theory / emotional 永远必检（人类最常踩这俩坑）
# - economic / cognitive 基础维度
MUST_CHECK = ["game_theory", "emotional", "cognitive", "economic"]
IMPORTANT = ["dialectical", "intuitive", "moral", "social"]
NICE_TO_HAVE = ["temporal", "metacognitive"]



def _keyword_match(text, keywords):
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False




def _score_verdict_candidate(sent: str, position_boost: float = 0.0) -> float:
    """
    评分一条 verdict 候选句。
    position_boost: 位置加成（越靠后越高，最多+0.15）
    """
    chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
    if chinese < 4:
        return 0.0

    # 长度分数（句子要够长才具体）
    len_score = min(chinese / 30.0, 1.0) * 0.25

    # 行动词（直接指示动作）
    action_kw = {
        "先", "应该", "可以", "建议", "推荐", "值得", "不要",
        "考虑", "评估", "权衡", "控制", "分散", "调研",
        "辞职", "创业", "买房", "移民", "借", "读研", "读博", "分手",
        "all in", "炒股", "考证", "考公", "健身", "换城市",
        "断舍离", "领养", "回老家", "原谅", "接受", "拒绝",
        "审慎", "谨慎", "果断", "立即", "保守", "激进",
        "留在", "离开", "接受", "放弃", "坚持", "改变",
    }
    action_cnt = sum(1 for kw in action_kw if kw in sent)
    action_score = min(action_cnt / 2.0, 1.0) * 0.35

    # 结论过渡词（"总之..."："我决定..."）
    conclusion_kw = {
        "总之", "综上", "最终决定", "最终建议", "最终", "综合来看",
        "综合考虑", "权衡之后", "权衡利弊", "经过分析",
    }
    conclusion_score = 0.2 if any(kw in sent for kw in conclusion_kw) else 0.0

    # 决策框架词（"我建议选A"："选A不选B"）
    decide_kw = {"选", "不选", "优先选", "主推", "更推荐", "更建议"}
    decide_score = 0.15 if any(kw in sent for kw in decide_kw) else 0.0

    # 模糊词（越少越好）
    vague_kw = {
        "不确定", "很难说", "更多信息", "无法判断",
        "具体情况具体分析", "基于", "给出判断", "需要更多信息",
        "再给出判断", "再综合考虑", "综合给出", "多维分析给出",
        "需要进一步", "有待观察", "视情况", "因人而异",
    }
    vague_penalty = sum(0.25 for kw in vague_kw if kw in sent)

    # 反向指标：还在说"还是"的 = 未决策
    indecisive = 0.1 if ("还是" in sent and "或者" in sent) else 0.0

    return max(0.0,
        len_score + action_score + conclusion_score + decide_score + position_boost
        - vague_penalty - indecisive
    )





def _synthesize_verdict(task_text: str, answers: dict) -> tuple:
    """
    从 LLM 直接输出的结论行提取 verdict：
    1. 优先取 ## 最终结论 行
    2. 其次取 => 结论行（取最后一个）
    3. 最后 fallback
    """
    if not answers:
        return ("需要更多信息才能判断", 0.3)

    # 合并所有维度的 content
    raw = ""
    for dim, ans in answers.items():
        if isinstance(ans, dict) and "content" in ans:
            raw += ans["content"]
        elif isinstance(ans, str):
            raw += ans
    raw = raw.strip()
    if not raw:
        return ("需要更多信息才能判断", 0.3)

    # Step 1: 优先取 ## 最终结论 行
    # 格式：## 最终结论[：:\s]+结论内容
    m_final = re.search(r'##\s*最终结论[：:\s]+(.+)', raw)
    if m_final:
        verdict = m_final.group(1).strip()
        if 5 <= len(verdict) <= 60:
            confidence = min(0.90, 0.50 + len(answers) * 0.05)
            return (verdict[:60], confidence)

    # Step 2: 取最后一个 => 结论行
    conclusion_lines = re.findall(r'=>\s*(.+)', raw)
    if conclusion_lines:
        verdict = conclusion_lines[-1].strip()
        if 5 <= len(verdict) <= 60:
            confidence = min(0.88, 0.45 + len(answers) * 0.05)
            return (verdict[:60], confidence)

    # Step 3: fallback
    confidence = 0.38 + len(answers) * 0.04
    return ("需要更多信息才能判断", confidence)
