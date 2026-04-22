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
import json
import re
from typing import Dict, List, Optional
from llm_adapter import get_adapter, CompletionRequest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

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



def _build_answer_prompt(task_text: str, questions: dict, agent_profile: dict = None,
                         prior_adj: dict = None, history_context: str = "",
                         bio_context: str = "",
                         profile_entries: list = None) -> str:
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
    # 生平事实参考（如果有）
    if bio_context:
        parts.insert(1, bio_context)
    # UnifiedProfile 标注注入（优先级：Fact > Pattern > Signal）
    if profile_entries:
        try:
            from judgment.user_model import UnifiedProfile
            profile_text = UnifiedProfile().to_prompt(profile_entries)
            if profile_text:
                parts.insert(1, "[User Profile — L1>L2>L3]\n" + profile_text)
        except Exception:
            pass

    return "\n".join(parts)



def _answer_questions(task_text: str, questions: dict, agent_profile: dict = None,
                      prior_adj: dict = None, history_context: str = "",
                      bio_context: str = "",
                      profile_entries: list = None) -> dict:
    """调用MiniMax LLM回答所有维度问题，返回 {dim_id: answer_text, ...}"""
    adapter = get_adapter()

    # 如果没有配置api_key（环境变量也没有），返回空
    if not adapter.is_configured():
        print("[LLM] MiniMax未配置 api_key，跳过answer生成")
        return {}

    prompt = _build_answer_prompt(task_text, questions, agent_profile, prior_adj,
                                  history_context, bio_context, profile_entries)

    # 截断prompt（LLM context limit）
    if len(prompt) > 6000:
        prompt = prompt[:6000] + "\n[内容过长已截断]"

    try:
        # 80秒超时，覆盖 retry 最大等待（5+15+30=50s + 读时间）
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(adapter.complete, CompletionRequest(
                prompt=prompt,
                max_tokens=2048,
                temperature=0.7,
            ))
            try:
                response = future.result(timeout=80)
            except FuturesTimeoutError:
                print("[LLM] API调用超时（80秒），跳过answer生成")
                return {}

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

        raw = response.content.strip()

        # ── 尝试 JSON 格式解析（MiniMax-M2 倾向返回 JSON）─────────────
        answers = {}
        dim_name_to_id = {
            "cognitive": "cognitive",
            "game_theory": "game_theory",
            "economic": "economic",
            "dialectical": "dialectical",
            "emotional": "emotional",
            "intuitive": "intuitive",
            "moral": "moral",
            "social": "social",
            "temporal": "temporal",
            "metacognitive": "metacognitive",
            # 中文别名
            "认知": "cognitive",
            "博弈": "game_theory",
            "经济": "economic",
            "辩证": "dialectical",
            "情绪": "emotional",
            "直觉": "intuitive",
            "道德": "moral",
            "社会": "social",
            "时间": "temporal",
            "元认知": "metacognitive",
        }

        # 1. 尝试 JSON array: [{"dimension": "...", "reason": "..."}, ...]
        try:
            # 找 JSON 数组
            json_match = re.search(r'\[\s*\{', raw)
            if json_match:
                json_str = raw[json_match.start():]
                # 补全可能的截断 JSON
                items = json.loads(json_str)
                for item in items:
                    dim_raw = item.get("dimension", item.get("dim", ""))
                    reason = item.get("reason", item.get("analysis", item.get("reasoning", "")))
                    dim_id = dim_name_to_id.get(dim_raw.lower(), dim_name_to_id.get(dim_raw))
                    if dim_id and reason:
                        answers[dim_id] = reason
        except Exception:
            pass

        # 2. 尝试单对象 JSON: {"dimension": "...", "reason": "..."}
        if not answers:
            try:
                # 去掉 markdown code block
                cleaned = re.sub(r'^```json\s*', '', raw)
                cleaned = _re.sub(r'^```\s*', '', cleaned)
                cleaned = cleaned.strip('` \n')
                obj = json.loads(cleaned)
                dim_raw = obj.get("dimension", obj.get("dim", ""))
                reason = obj.get("reason", obj.get("analysis", obj.get("reasoning", "")))
                dim_id = dim_name_to_id.get(dim_raw.lower(), dim_name_to_id.get(dim_raw))
                if dim_id and reason:
                    answers[dim_id] = reason
            except Exception:
                pass

        # 3. 行解析（原有格式：【维度名】内容）
        if not answers:
            answers = {}
            dim_labels_inv = {
                "【认知维度】": "cognitive",
                "【博弈维度】": "game_theory",
                "【经济维度】": "economic",
                "【辩证维度】": "dialectical",
                "【情绪维度】": "emotional",
                "【直觉维度】": "intuitive",
                "【道德维度】": "moral",
                "【社会维度】": "social",
                "【时间维度】": "temporal",
                "【元认知维度】": "metacognitive",
                # ## 标题格式（无【】）
                "## 认知": "cognitive",
                "## 博弈": "game_theory",
                "## 经济": "economic",
                "## 辩证": "dialectical",
                "## 情绪": "emotional",
                "## 直觉": "intuitive",
                "## 道德": "moral",
                "## 社会": "social",
                "## 时间": "temporal",
                "## 元认知": "metacognitive",
                # 中文维度名（无括号）
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

            current_dim = None
            current_content = []

            for line in raw.split("\n"):
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
        current_dim = None
        current_content = []

        for line in raw.split("\n"):
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
                # 去除【】标题，只保留后面的内容
                for sep in ["】", "##", "：", "： "]:
                    if sep in line:
                        rest = line.split(sep, 1)
                        content = rest[1].strip() if len(rest) > 1 else ""
                        if content:
                            current_content.append(content)
                        break
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





def _extract_sentences(text: str) -> list:
    """将文本切分为句子列表（句号/感叹号/问号分隔）"""
    # 用省略号分隔防止"综合以上分析，建议..."被当作一句
    text2 = text.replace('...', '<<<SEP>>>').replace('……', '<<<SEP>>>')
    parts = re.split(r'([。！？])', text2)
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sent = parts[i].strip()
        punct = parts[i + 1]
        combined = sent + punct if punct else sent
        if sent:
            sentences.append(combined)
    if len(parts) % 2 == 1 and parts[-1].strip():
        sentences.append(parts[-1].strip())
    return sentences


def _clean_thinking_blocks(text: str) -> str:
    """
    清理 XML thinking/reasoning 标签块，同时保留正文内容。
    MiniMax 的 <reasoning>...</reasoning> 块里往往有大量思考过程，
    但有时也会包含具体的维度和结论，需要从末尾提取。
    """
    # 策略：把 <reasoning>...</reasoning> 整体当作正文末尾的候选区
    # 但先提取所有正文部分
    cleaned = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)  # 去掉其余 XML 标签
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _synthesize_verdict(task_text: str, answers: dict) -> tuple:
    """
    从 LLM 输出合成 verdict（句子级评分版）：
    1. 优先取 ## 最终结论 / ## 最终判断 格式结构
    2. 正文句子级评分（行动词+结论词加权，模糊词/犹豫扣分）
    3. thinking block 末尾加权（+0.15 位置加成）
    4. 取最高分句子，阈值 0.08
    """
    if not answers:
        return ("需要更多信息才能判断", 0.3)

    # 1. 合并所有维度的 content
    raw = ""
    for dim, ans in answers.items():
        if isinstance(ans, dict) and "content" in ans:
            raw += ans["content"]
        elif isinstance(ans, str):
            raw += ans
    raw = raw.strip()
    if not raw:
        return ("需要更多信息才能判断", 0.3)

    # 2. 清理 XML 标签
    after = _clean_thinking_blocks(raw)

    # 3. Step 0: 优先取 ## 最终结论 / ## 最终判断
    m_final = re.search(
        r'##\s*最终(结论|判断|建议)[：:\s]+(.+)', after, re.DOTALL)
    if m_final:
        verdict = m_final.group(2).strip()[:60]
        if len(verdict) >= 4:
            confidence = min(0.90, 0.50 + len(answers) * 0.05)
            return (verdict, confidence)

    # 4. Step 1: 正文（非 thinking block）句子级评分选最佳
    best_score = 0.0
    best_sent = ""
    for sent in _extract_sentences(after):
        s = _score_verdict_candidate(sent)
        if s > best_score:
            best_score = s
            best_sent = sent[:60]
    if best_score >= 0.08 and best_sent:
        confidence = min(0.88, 0.42 + best_score * 0.3 + len(answers) * 0.03)
        return (best_sent, confidence)

    # 5. Step 2: 从 thinking blocks 提取（MiniMax 主要内容在 <reasoning> 里）
    thinking_blocks = re.findall(
        r'<reasoning>(.*?)</reasoning>', raw, re.DOTALL)
    if not thinking_blocks:
        # fallback: 也找 <think>
        thinking_blocks = re.findall(
            r'<think>(.*?)</think>', raw, re.DOTALL)

    best_score2 = 0.0
    best_sent2 = ""
    for idx, block in enumerate(thinking_blocks):
        block_clean = re.sub(r'<[^>]+>', '', block).strip()
        position_boost = 0.15 * (idx + 1) / max(len(thinking_blocks), 1)
        for sent in _extract_sentences(block_clean):
            s = _score_verdict_candidate(sent, position_boost=position_boost)
            if s > best_score2:
                best_score2 = s
                best_sent2 = sent[:60]

    if best_score2 >= 0.08 and best_sent2:
        confidence = min(0.85, 0.40 + best_score2 * 0.3 + len(answers) * 0.03)
        return (best_sent2, confidence)

    # 6. Step 3: 取最后一个 => 结论行（降级兜底）
    conclusion_lines = re.findall(r'=>\s*(.+)', raw)
    if conclusion_lines:
        verdict = conclusion_lines[-1].strip()[:60]
        if len(verdict) >= 4:
            return (verdict, 0.42 + len(answers) * 0.04)

    # 7. Fallback: 最高分正文句子
    if best_sent:
        return (best_sent, 0.38 + len(answers) * 0.03)

    confidence = 0.38 + len(answers) * 0.04
    return ("需要更多信息才能判断", confidence)
