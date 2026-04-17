# ⚖️ Juhuo — Judgment System

**An evolving AI agent that mimics a specific individual, then surpasses human-level judgment.**

> _Not a tool. A digital alter-ego that grows over time._

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置
python -m juhuo config init  # 创建配置模板

# 自检
python -m juhuo test

# CLI 判断
python -m juhuo "要不要辞职创业？"

# 交互模式
python -m juhuo shell

# Web Console
python -m juhuo web

# Benchmark
python -m juhuo benchmark
```

---

## 核心功能

### 1. 十维判断 (Judgment)

| 维度 | 来源 | 作用 |
|------|------|------|
| 认知心理学 | 卡尼曼 System 1/2 | 偏差检测、元认知 |
| 博弈论 | 纳什均衡/激励结构 | 玩家分析、策略推演 |
| 经济学 | 机会成本/边际分析 | 看清代价 |
| 辩证唯物主义 | 实事求是/矛盾分析 | 事实先行 |
| 情绪智能 | Goleman 情绪智能 | 识别情绪信号 |
| 直觉/第六感 | System 1 模式识别 | 快速判断 |
| 价值/道德推理 | 伦理学 | 应不应该 |
| 社会意识 | 群体心理学 | 识别从众压力 |
| 时间折扣 | 行为经济学 | 对抗人类短视 |
| 元认知 | 自我监控 | 思考我在怎么思考 |

### 2. 闭环进化

```
判断 → 记录因果链 → 用户反馈 → 更新信念 → 下次判断改善
```

### 3. 自进化引擎

- **Self-Evolver**: 自动识别模式 → 写规则 → 防止下次犯错
- **Skill Evolver**: 追踪成功率 → 调整触发条件 → 合并相似 Skill
- **Benchmark**: 8 案例测试集 → 维度准确率 → 最弱维度优先修复

### 4. Claude Code / Codex / OpenClaw 启发

| 特性 | 来源 | 文件 |
|------|------|------|
| Verification Agent | Claude Code | `judgment/verification_agent.py` |
| Tool Governance (14步) | Claude Code | `judgment/tool_governance.py` |
| 四道压缩 | Claude Code | `judgment/compactor_v2.py` |
| Skills 按需加载 | OpenClaw | `skills/skill_loader.py` |
| Hook 系统 (17事件) | OpenClaw | `judgment/openclaw_hooks.py` |
| Session 管理 | OpenClaw | `judgment/session.py` |

### 5. QwenPaw 启发

| 特性 | 文件 |
|------|------|
| LLM 限流 (QPM/并发) | `llm_adapter/rate_limiter.py` |
| Retry + Backoff | `llm_adapter/rate_limiter.py` |
| 类型安全配置 | `config/env_loader.py` |

---

## CLI 命令

```bash
# 判断
python -m juhuo "要不要移民？"

# 交互
python -m juhuo shell

# Web
python -m juhuo web --port 18768

# 状态
python -m juhuo status

# Verdict 管理
python -m juhuo verdict list
python -m juhuo verdict correct <chain_id>
python -m juhuo verdict wrong <chain_id>

# 配置
python -m juhuo config show
python -m juhuo config init
python -m juhuo config edit

# 自检
python -m juhuo test

# Benchmark
python -m juhuo benchmark
```

---

## Web Console

访问 `http://localhost:18768`

- 主页：判断输入 + 维度可视化
- `/status`：系统状态
- `/history`：判断历史
- `/api/judge`：REST API

---

## 配置

```bash
# 配置文件: ~/.juhuo/.env
MINIMAX_API_KEY=your_key_here
DEFAULT_PROVIDER=minimax
DEFAULT_MODEL=minimax-01

# LLM 限流（可选）
LLM_MAX_CONCURRENT=10
LLM_MAX_QPM=600
LLM_MAX_RETRIES=3
```

---

## 架构

```
judgment/          # 十维判断（23个.py）
├── pipeline.py    # 完整流水线
├── dynamic_weights.py  # 动态权重
├── benchmark.py   # 质量评估
├── self_test.py   # 自检
├── verification_agent.py  # 验证
├── tool_governance.py  # 工具治理
├── compactor_v2.py  # 四道压缩
├── openclaw_hooks.py  # Hook系统
└── session.py      # Session管理

causal_memory/     # 因果记忆
self_model/       # 自我模型
skills/           # Skills自进化
llm_adapter/      # LLM适配器+限流
config/           # 配置系统
```

---

## 设计原则

1. **铁律一**: 模拟人类意识，思想超越人类
2. **铁律二**: 模仿具体个人，超越人类整体
3. **闭环**: 判断 → 记录 → 反馈 → 进化
4. **可追溯**: 每次判断都有 chain_id

---

## License

MIT
