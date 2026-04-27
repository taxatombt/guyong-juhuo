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
                         profile_entries: list = None,
                         lessons_context: str = "",
                         pet_context: str = "") -> str:
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
    # 宠物状态注入（排在 UnifiedProfile 之前）
    if pet_context:
        parts.insert(1, pet_context)

    # UnifiedProfile 标注注入（优先级：Fact > Pattern > Signal）
    if profile_entries:
        try:
            from judgment.user_model import UnifiedProfile
            profile_text = UnifiedProfile().to_prompt(profile_entries)
            if profile_text:
                parts.insert(1, "[User Profile — L1>L2>L3]\n" + profile_text)
        except Exception:
            pass

    # 历史教训注入（来自因果链经验，不是通用知识）
    if lessons_context:
        parts.insert(1, lessons_context)

    return "\n".join(parts)



def _answer_questions(task_text: str, questions: dict, agent_profile: dict = None,
                      prior_adj: dict = None, history_context: str = "",
                      bio_context: str = "",
                      profile_entries: list = None,
                      lessons_context: str = "",
                      pet_context: str = "") -> dict:
    """调用MiniMax LLM回答所有维度问题，返回 {dim_id: answer_text, ...}"""
    adapter = get_adapter()

    # 如果没有配置api_key（环境变量也没有），返回空
    if not adapter.is_configured():
        print("[LLM] MiniMax未配置 api_key，跳过answer生成")
        return {}

    prompt = _build_answer_prompt(task_text, questions, agent_profile, prior_adj,
                                  history_context, bio_context, profile_entries,
                                  lessons_context, pet_context)

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
def _extract_action_from_verdict(verdict):
    """Chinese: verdict extract"""
    import re
    for pat, tag in [
        ('[建议]([^\s，。；!?]{2,15})', 's'),
        ('[不要]([^\s，。；!?]{2,10})', 'w'),
        ('[应该]([^\s，。；!?]{2,10})', 's'),
        ('[可以]([^\s，。；!?]{2,10})', 'c'),
        ('[推荐]([^\s，。；!?]{2,10})', 'r'),
        ('[值得]([^\s，。；!?]{2,10})', 'v'),
    ]:
        m = re.search(pat, verdict)
        if m:
            return m.group(0).strip(), 'v:' + tag
    for kw in ['不要','all in','保守','激进','控制仓位',
                '分散','全仓','先做','先看','先评估',
                '辛职','跳槐','创业','留在','接受',
                '拒绝','买房','移民','读研','分手',
                '坚持','改变','审慎','谨慎','枬断']:
        if kw in verdict:
            idx = verdict.index(kw)
            return verdict[idx:idx+12].strip(), 'kw:' + kw
    if len(verdict) >= 6:
        return verdict[:18], 'prefix'
    return verdict, 'fallback'



def _llm_predict_choice(task_text, answers):
    """Chinese: LLM fallback for prediction"""
    import re
    dim_sum = ""
    for dim, ans in list(answers.items())[:5]:
        if isinstance(ans, dict) and "content" in ans:
            c = re.sub(r"<[^>]+>", "", ans["content"])[:120]
        elif isinstance(ans, str):
            c = re.sub(r"<[^>]+>", "", ans)[:120]
        else:
            c = str(ans)[:120]
        dim_sum += "[%s] %s\n" % (dim[:12], c)
    p = ("\u4efb\u52a1\uff1a%s\n\u7528\u6237\u753b\u50cf\u53c2\u8003\uff1a\n%s\n"
         "\u8bf7\u9884\u6d4b\uff1a\u8fd9\u4e2a\u7528\u6237\u6700\u7ec8\u6700\u53ef\u80fd"
         "\u9009\u62e9\u4ec0\u4e48\u884c\u52a8\uff1f\u53ea\u8f93\u51fa\u4e00\u4e2a\u7b80"
         "\u77ed\u884c\u52a8\uff08\u4e0d\u8d85\u8fc720\u5b57\uff09\uff1a\n"
         "\u9884\u6d4b\u884c\u52a8\uff1a[\u5177\u4f53\u884c\u52a8]") % (task_text, dim_sum)
    try:
        from judgment.llm_calls import get_adapter
        a = get_adapter()
        if not a or not a.is_configured():
            raise ValueError("no adapter")
        req = type("CR",(),{"prompt":p,"max_tokens":300,"temperature":0.3})()
        r = a.complete(req)
        txt = r if isinstance(r,str) else getattr(r,"content",str(r))
        m = re.search(r"[\u9884\u6d4b][\u884c\u52a8][\uff1a:]\s*([^\n]{2,25})", txt)
        if m:
            return {"predicted_action":m.group(1).strip(),"prediction_confidence":0.55,"reasoning":"llm","source":"llm"}
        lines = [l.strip() for l in txt.split("\n") if l.strip() and len(l.strip())>=4]
        if lines:
            return {"predicted_action":lines[0][:20],"prediction_confidence":0.50,"reasoning":"llm_raw","source":"llm"}
    except Exception:
        pass
    return {"predicted_action":"\u672a\u77e5","prediction_confidence":0.30,"reasoning":"no_adapter","source":"none"}


def predict_user_choice(task_text, answers, verdict, confidence):
    """Chinese: core predict function"""
    action, reason = _extract_action_from_verdict(verdict)
    if action and action != "\u672a\u77e5" and len(action) >= 2:
        return {
            "predicted_action": action,
            "prediction_confidence": min(0.90, confidence + 0.08),
            "reasoning": reason,
            "source": "verdict_extraction",
        }
    return _llm_predict_choice(task_text, answers)



def _verify_judgment(task_text: str, answers: dict, verdict: str, confidence: float) -> dict:
    """
    Self-Verification: 检测判断中的逻辑矛盾（Anthropic Building Effective AI Agents启发）

    不触发额外LLM调用。
    - 用关键词检测推荐方向（支持/反对/中立）
    - 方向冲突的维度对 = 矛盾
    - flags: 具体矛盾描述
    - warnings: 置信度不一致等软警告
    - verification_score: 1.0=完全一致, 0.0=严重矛盾
    """
    import re

    flags = []
    warnings = []

    # 推荐方向检测关键词
    PRO_ACTION = {"建议", "支持", "推荐", "倾向", "鼓励", "可以", "可行", "值得",
                   "应该", "鼓励", "高", "强", "重要", "显著", "all in", "果断"}
    CON_ACTION = {"不建议", "反对", "谨慎", "慎重", "警告", "不建议", "不行",
                   "不可", "不要", "避免", "风险", "保守", "低", "弱", "不重要"}
    # 经济/时间维度专用：高分=高风险（反对行动），低分=可接受
    HIGH_RISK = {"风险", "高风险", "极高风险", "风险较大", "不建议"}

    def get_direction(ans) -> str:
        """从文本判断推荐方向：pro/con/neutral（两步避免双重计算）"""
        text = ans.get("content", "") if isinstance(ans, dict) else str(ans)
        pro, con = 0, 0
        # 第一步：找出所有被否定的位置
        NEG_CHARS = "不别非无未"
        negated_positions = set()
        # 否定关键词对：neg_char + keyword
        for neg_char in NEG_CHARS:
            for kw in sorted(PRO_ACTION | CON_ACTION, key=len, reverse=True):
                needle = neg_char + kw
                start = 0
                while True:
                    idx = text.find(needle, start)
                    if idx < 0:
                        break
                    # 标记从idx到idx+len(needle)的所有位置为已否定
                    for j in range(idx, idx + len(needle)):
                        negated_positions.add(j)
                    start = idx + 1
        # 否定短语
        for neg_phrase in ("反对", "不建议", "不支持", "不可", "不要", "不建议"):
            start = 0
            while True:
                idx = text.find(neg_phrase, start)
                if idx < 0:
                    break
                for j in range(idx, idx + len(neg_phrase)):
                    negated_positions.add(j)
                start = idx + 1

        def is_negated(pos, kw_len):
            """检查从pos开始的kw_len个字符是否在否定位置中"""
            return any(j in negated_positions for j in range(pos, pos + kw_len))

        # 第二步：统计未被否定的关键词
        for kw in sorted(PRO_ACTION, key=len, reverse=True):
            start = 0
            while True:
                idx = text.find(kw, start)
                if idx < 0:
                    break
                if not is_negated(idx, len(kw)):
                    pro += 1
                start = idx + 1

        for kw in sorted(CON_ACTION, key=len, reverse=True):
            start = 0
            while True:
                idx = text.find(kw, start)
                if idx < 0:
                    break
                if not is_negated(idx, len(kw)):
                    con += 1
                start = idx + 1

        # 高风险关键词（独立检测，不被其他否定覆盖）
        for kw in HIGH_RISK:
            if kw in text:
                con += 2

        if pro > con + 1: return "pro"
        elif con > pro + 1: return "con"
        return "neutral"


    # 1. 检测维度间的推荐方向矛盾
    dim_directions = {}
    for dim_id, ans in answers.items():
        dim_directions[dim_id] = get_direction(ans)

    # 矛盾对：一方pro，另一方con
    contradiction_pairs = [
        ("cognitive", "emotional"),
        ("cognitive", "intuitive"),
        ("cognitive", "economic"),
        ("cognitive", "temporal"),
        ("game_theory", "emotional"),
        ("game_theory", "intuitive"),
        ("game_theory", "economic"),
        ("emotional", "cognitive"),
        ("emotional", "game_theory"),
        ("emotional", "intuitive"),
        ("economic", "cognitive"),
        ("economic", "game_theory"),
        ("economic", "social"),
        ("intuitive", "cognitive"),
        ("intuitive", "economic"),
        ("intuitive", "temporal"),
    ]

    contradiction_count = 0
    for dim_a, dim_b in contradiction_pairs:
        dir_a = dim_directions.get(dim_a)
        dir_b = dim_directions.get(dim_b)
        if dir_a == "pro" and dir_b == "con":
            contradiction_count += 1
            flags.append(f"方向冲突: {dim_a}(建议{chr(24320)}) vs {dim_b}(建议{chr(21453)})")
        elif dir_a == "con" and dir_b == "pro":
            contradiction_count += 1
            flags.append(f"方向冲突: {dim_a}(建议{chr(21453)}) vs {dim_b}(建议{chr(24320)})")

    # 2. Verdict 与维度方向一致性
    verdict_direction = get_direction({"content": verdict})
    dim_pro_count = sum(1 for d in dim_directions.values() if d == "pro")
    dim_con_count = sum(1 for d in dim_directions.values() if d == "con")
    majority = "pro" if dim_pro_count > dim_con_count else "con"

    verdict_dimension_agreement = 0
    if verdict_direction == majority:
        verdict_dimension_agreement = 1
    elif verdict_direction != "neutral" and majority != "neutral":
        verdict_dimension_agreement = -0.3  # verdict与多数维度不一致

    # 3. 置信度与一致性一致性
    if dim_directions:
        neutral_count = sum(1 for d in dim_directions.values() if d == "neutral")
        consistent_count = len(dim_directions) - neutral_count
        consistency_ratio = consistent_count / len(dim_directions)
        if consistency_ratio < 0.5 and confidence > 0.7:
            warnings.append(f"置信度高({confidence:.2f})但维度方向混乱(仅{consistent_count}/{len(dim_directions)}一致)")

    # 4. 计算综合验证分数
    base = 1.0
    base -= min(0.4, contradiction_count * 0.08)
    base += verdict_dimension_agreement * 0.15
    base -= len(warnings) * 0.05
    verification_score = max(0.0, min(1.0, base))

    return {
        "verification_score": round(verification_score, 3),
        "flags": flags,
        "warnings": warnings,
        "contradiction_count": contradiction_count,
        "dim_directions": {k: v for k, v in dim_directions.items() if v != "neutral"},
    }


