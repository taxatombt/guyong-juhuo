# ⚖️ guyong-juhuo · 判断系统

<p align="center">
  <img src="logo_preview.png" width="480" alt="juhuo logo">
</p>

**An evolving personal AI agent that mimics a specific individual, then surpasses human-level judgment.**

> 不是工具。是一个会随时间成长的数字分身。

---

## 这是什么

guyong-juhuo 是一个 **12子系统 AI Agent 框架**，基于 LLM 后端（MiniMax / OpenAI / Ollama）。它在 10 个认知维度上模拟特定个人的判断模式，通过闭环反馈不断进化，直到判断力超越人类整体。

核心区别：大多数 AI Agent 优化"什么是正确的"。guyong-juhuo 优化**"这个特定的人会怎么决定，为什么"**——然后闭环让系统越变越好。

---

## 12 个子系统

| # | 子系统 | 功能 |
|---|--------|------|
| 1 | **Judgment** | 十维并行评估（认知 · 博弈论 · 经济 · 辩证 · 情绪 · 直觉 · 道德 · 社会 · 时间折扣 · 元认知） |
| 2 | **Causal Memory** | 快慢双通道：即时记录 + 批量因果推理 |
| 3 | **Curiosity Engine** | 双随机游走（80% 目标驱动 / 20% 自由探索），Ralph 循环终止 |
| 4 | **Goal System** | 洋葱分层：5年 → 年度 → 月度 → 周 → 今日 |
| 5 | **Self-Model** | 贝叶斯盲点追踪：积累"我容易在这里犯错" |
| 6 | **Emotion System** | PAD 三维模型（愉悦 × 唤醒 × 支配）；情绪是信号，不是噪音 |
| 7 | **Self-Evolution** | 闭环：每次错误 → 分析 → 写规则 → 防止下次再犯 |
| 8 | **Output System** | 决定什么时候说话、什么时候沉默；P0-P4 优先级格式化 |
| 9 | **Action System** | 四象限紧急度 × 重要性排序 + 执行信号生成 |
| 10 | **Perception Layer** | 注意力过滤器 + Web + PDF + RSS + 邮件适配器 |
| 11 | **Skill Evolution** | 自动检测技能冲突 + 自主改进低性能技能 |
| 12 | **Feedback System** | 双循环：判断层 + 进化层，5层自我防御钩子 |

---

## 两种模式

| 模式 | 说明 |
|------|------|
| **Mimic Mode** | 传入 `agent_profile` — 系统强制对齐该人的判断风格 |
| **Transcend Mode** | 10个通用维度；无 profile — 系统基于纯推理判断，闭环直到超越人类 |

**铁律：** _模仿具体个人，超越人类整体。_

---

## 快速开始

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
pip install -r requirements.txt

# CLI 判断
python cli.py "要不要辞职创业？"

# Web Console
python cli.py web

# 查看状态
python cli.py status

# 自检
python cli.py test
```

---

## 判断输出示例

```
=== 判断: "要不要辞职创业？" ===

  cognitive       ████████████████░░  82%  "需要更多薪资数据"
  game_theory     █████████████░░░░░  75%  "反要约风险"
  economic        ████████████████░░  85%  "35%薪资差距值得考虑"
  dialectical     ███████████████░░░  78%  "双方都有道理"
  emotional       ████████████░░░░░░  65%  "对后悔的焦虑"
  intuitive      ███████████████░░░  80%  "外面有更好的机会"
  moral           ████████████░░░░░░  70%  "对家庭的责任"
  social          ██████████░░░░░░░░  60%  "网络机会成本"
  temporal        ██████████████░░░  72%  "3个月窗口最优"
  metacognitive   ███████████████░░░  79%  "当前分析过于自信"

  → 建议: 谨慎考虑（置信度: 高, 81%）
  → chain_id: j_1776149590792
```

---

## 架构

```
Perception  →  Attention Filter  →  Judgment (10D)
                                           ↓
                                    Causal Memory
                                           ↓
                                     Self-Model
                                           ↓
                                   Closed Feedback Loop
                                    ↕ (verdict signals)
                                   Evolver
                                           ↓
                                   Skill Evolution
```

闭环：判断 → 记录链 → 用户反馈 verdict → 信念更新 → 下次判断改善

---

## 技术栈

- **Python 3.11+** (核心逻辑)
- **MiniMax / OpenAI / Ollama** (LLM 后端)
- **Flask** (Web Console)
- **SQLite** (判断链 + 信念滚动缓冲)

---

## 安装

```bash
pip install -r requirements.txt
python cli.py web
# 访问 http://localhost:18768
```

---

## 配置

```
~/.juhuo/.env       — API keys（最高优先级，不提交 git）
```

首次配置：
```bash
python cli.py config init  # 创建配置模板
python cli.py config edit  # 编辑配置
```

---

## CLI 命令

```bash
python cli.py "问题"         # 单次判断
python cli.py shell         # 交互模式
python cli.py web           # Web Console
python cli.py status         # 状态查看
python cli.py verdict list   # 判断历史
python cli.py verdict correct <id>   # 标记正确
python cli.py verdict wrong <id>     # 标记错误
python cli.py config show    # 显示配置
python cli.py config init    # 初始化配置
python cli.py test           # 自检
python cli.py benchmark      # Benchmark 测试
```

---

## 设计原则

- **铁律保护核心身份** — 某些特质不能被进化掉
- **Fitness = "与你是谁一致"** — 不是"通用标准认为正确的"
- **完整版本快照** — 任何历史状态都可恢复
- **判断链滚动缓冲** — SQLite，100条上限
- **有限信念更新** — 每次 verdict 最多 10% 变化，饱和在 0.05 / 0.95

---

## TODO（下次版本）

> 现在最缺的不是新功能，是把 Self-Evolver 从「能跑」变成「能验证」。

- [ ] **Verdict 数据积累** — 目标 50+ 条，覆盖多场景
- [ ] **Self-Evolver 验证闭环** — verify_evolution() + 自动验证 + 回滚
- [ ] **生产配置参数** — BIAS=3, MIN_SAMPLES=5, COOLDOWN=24h
- [ ] **GDPVal Benchmark** — 用标准案例集评估判断质量
- [x] apply_evolved_weights 落地（v1.5）
- [x] Verdict 自动积累（v1.5）
- [x] evolution_validator 追踪（v1.5）

---

## 版本更新

### v1.5.2 (2026-04-17)

新增：
- **Claude Code 启发**：Verification Agent + Tool Governance (14步) + 四道压缩
- **OpenClaw 启发**：Skills 按需加载 + Hook 系统 (17事件) + Session 管理
- **QwenPaw 启发**：LLM 限流 (QPM/并发) + Retry + Backoff + EnvVarLoader
- **Web Console**：Flask 界面 + REST API
- **Benchmark**：8案例测试集，维度准确率评估
- **Self-Test**：6项启动自检
- **MCP Server**：judgment_10d / judgment_verdict / judgment_status
- **i18n**：多语言支持 (zh_CN / en_US)
- **Docker**：Dockerfile + docker-compose.yml

### v1.5.0 (2026-04-14)

初始版本，10维判断框架 + 因果记忆 + 自我模型

---

<p align="center">
  <a href="https://github.com/taxatombt/guyong-juhuo">GitHub</a> ·
  <a href="https://github.com/taxatombt/guyong-juhuo/releases">Releases</a>
</p>
