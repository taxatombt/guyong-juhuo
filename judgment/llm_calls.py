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



def _build_answer_prompt(task_text: str, questions: dict, agent_profile: dict = None) -> str:
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

    return "\n".join(parts)



def _answer_questions(task_text: str, questions: dict, agent_profile: dict = None) -> dict:
    """调用MiniMax LLM回答所有维度问题，返回 {dim_id: answer_text, ...}"""
    adapter = get_adapter()

    # 如果没有配置api_key（环境变量也没有），返回空
    if not adapter.is_configured():
        print("[LLM] MiniMax未配置 api_key，跳过answer生成")
        return {}

    prompt = _build_answer_prompt(task_text, questions, agent_profile)

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




def _synthesize_verdict(task_text: str, answers: dict) -> tuple:
    """
    基于各维度回答合成 verdict 和 confidence
    返回 (verdict_str, confidence_float)
    """
    if not answers:
        return ("需要更多信息才能判断", 0.3)
    try:
        raw = ""
        for dim, ans in answers.items():
            if isinstance(ans, dict) and "content" in ans:
                raw += ans["content"]
            elif isinstance(ans, str):
                raw += ans
        raw = raw.strip()
        if not raw:
            raise ValueError("No content")

        def score_sent(sent: str) -> float:
            chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
            if chinese < 4:
                return 0.0
            len_score = min(chinese / 30.0, 1.0) * 0.3
            action_kw = {"先", "应该", "可以", "建议", "推荐", "值得", "不要",
                        "考虑", "评估", "权衡", "控制", "分散", "调研",
                        "辞职", "创业", "买房", "移民", "借", "读研", "读博", "分手",
                        "all in", "炒股", "考证", "考公", "健身", "换城市",
                        "断舍离", "领养", "回老家", "原谅", "接受", "拒绝",
                        "审慎", "谨慎", "果断", "立即", "保守", "激进"}
            action_cnt = sum(1 for kw in action_kw if kw in sent)
            action_score = min(action_cnt / 2.0, 1.0) * 0.4
            vague_kw = {"不确定", "很难说", "更多信息", "无法判断",
                         "具体情况具体分析", "基于", "给出判断", "需要更多信息",
                         "再给出判断", "再综合考虑", "综合给出", "多维分析给出"}
            vague_penalty = sum(0.3 for kw in vague_kw if kw in sent)
            return max(0.0, len_score + action_score - vague_penalty)

        def extract_sentences(text: str) -> list:
            """句子提取：句号 + 省略号分隔（处理无句号段落）"""
            # 先清理残留的 thinking 标签
            text = re.sub(r'^好了?\s*', '', text)
            text = re.sub(r'好了?\s*$', '', text)
            text = re.sub(r'^<think>\s*', '', text)
            text = re.sub(r'<think>\s*$', '', text)
            text = re.sub(r'@\d{10,}', '', text)  # 去掉 @时间戳
            SEP = '<<<SEP>>>'
            text2 = text.replace('...', SEP)
            parts = re.split(r"([。！？])", text2)
            sents = []
            for i in range(0, len(parts) - 1, 2):
                part = parts[i].strip()
                sep = parts[i + 1]
                sent = part + (sep if sep else '')
                if sent.strip():
                    sents.append(sent.strip().replace(SEP, '...'))
            if len(parts) % 2 == 1 and parts[-1].strip():
                last = parts[-1].strip().replace(SEP, '...')
                if last:
                    sents.append(last)
            return sents

        # Step 1: 清理正文残留 thinking 标签
        after = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Step 2: 从正文（非 thinking block）提取句子
        best_score = -1.0
        best_sent = ""
        if after:
            for sent in extract_sentences(after):
                chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese >= 4 and chinese / max(len(sent), 1) > 0.5:
                    s = score_sent(sent)
                    if s > best_score:
                        best_score = s
                        best_sent = sent[:50]
        if best_score >= 0.15:
            confidence = min(0.88, 0.35 + len(answers) * 0.08)
            return (best_sent, confidence)

        # Step 3: 从所有 thinking blocks 扫描，选最佳句子（句子级，非 block 级）
        blocks = re.findall(r"<think>.*?</think>", raw, re.DOTALL)
        for block in blocks:
            # 提取 thinking block 的文本内容（去掉标签）
            block_text = re.sub(r'^<think>', '', block)
            block_text = re.sub(r'</think>$', '', block_text)
            block_clean = re.sub(r'^\s*(好的|嗯|下面|综合|根据|经过).*?[:：]', "", block_text)
            block_clean = re.sub(r'Count[:：].*$', "", block_clean, flags=re.DOTALL)
            block_clean = re.sub(r'字数[:：].*$', "", block_clean, flags=re.DOTALL)
            block_clean = re.sub(r'[A-Za-z\u4e00-\u9fff]\s*\(\d+\)', "", block_clean)
            # 逐句评分
            for sent in extract_sentences(block_clean):
                chinese = len(re.findall(r'[\u4e00-\u9fff]', sent))
                if chinese >= 4 and chinese / max(len(sent), 1) > 0.5:
                    s = score_sent(sent)
                    if s > best_score:
                        best_score = s
                        best_sent = sent[:50]
        if best_sent:
            confidence = min(0.88, 0.35 + len(answers) * 0.08)
            return (best_sent, confidence)

        # Step 4: Fallback
        total_expected = len(answers) + 3
        confidence = min(0.9, len(answers) / total_expected + 0.2)
        return (f"基于{len(answers)}个维度的分析给出了判断", confidence)
    except Exception:
        return ("需要更多信息才能判断", 0.3)

