# juhuo 项目索引

> 通用 AI agent 框架：模拟一个人，全面超越那个人。
> 版本：v1.3 | 最新 commit：c2f1138

---

## 核心文档

| 文件 | 内容 |
|------|------|
| `PROJECT_INDEX.md` | 本文件，项目集中索引 |
| `PROJECT_INTRO.md` | 项目介绍 |
| `CHANGELOG.md` | 主变更日志 |
| `changelogs/v1.1.md` | v1.1 详情 |
| `changelogs/v1.2.md` | v1.2 详情 |
| `SKILL.md` | Skill 系统 |
| `INSTALL_GUIDE.md` | 安装指南 |
| `LIFE_OS.md` | 人生操作系统 |

---

## 12个子系统速查

| # | 子系统 | 核心文件 | 状态 |
|---|--------|---------|------|
| 1 | Judgment | `judgment/router.py` | ✅ |
| 2 | Causal Memory | `causal_memory/causal_memory.py` | ✅ |
| 3 | Curiosity Engine | `curiosity/` | ✅ |
| 4 | Goal System | `goal_system/` | ✅ |
| 5 | Self-Model | `self_model/` | ✅ |
| 6 | Emotion System | `emotion_system/` + `judgment/emotion_adapter.py` | ✅ |
| 7 | Self-Evolution | `judgment/self_evolver.py` | ✅ |
| 8 | Output System | `output/` | ✅ |
| 9 | Action System | `action_system/` | ✅ |
| 10 | Perception Layer | `perception/` | ✅ |
| 11 | Skill Evolution | `openspace/` | ✅ |
| 12 | Feedback System | `feedback_system/` | ✅ |

---

## 三种模拟用户的方式

| 途径 | 来源 | 文件 |
|------|------|------|
| biography | 用户自述生平（静态）| `causal_memory/biography.py` |
| experiences | 做过的决策 + outcome（流式）| `causal_memory/` + `judgment/closed_loop.py` |
| behavior | juhuo实际工具调用（行为日志）| `judgment/behavior_logger.py` |

---

## 核心闭环

```
check10d_run()
  → snapshot_judgment(verdict + predicted_action)
  → receive_verdict(correct, outcome_score)
    → UPDATE dimension_beliefs
    → record_outcome → experiences
    → evolver.record_outcome
  → receive_actual_choice()
    → compare predicted vs actual
    → receive_verdict()

维度信念：max 10% 变化，饱和 0.05 / 0.95
```

---

## 关键文件索引

### 判断层
- `judgment/router.py` — check10d_run / check10d_and_execute（入口）
- `judgment/closed_loop.py` — receive_verdict / receive_actual_choice（闭环）
- `judgment/self_evolver.py` — EvolverScheduler / 维度权重闭环
- `judgment/benchmark.py` — GDPVal 22-case 评估
- `judgment/lessons.py` — 因果链教训层
- `judgment/behavior_logger.py` — 途径3：行为日志
- `judgment/emotion_adapter.py` — PAD情绪 → 维度调制
- `judgment/pre_tool_hook.py` — PreToolUse 钩子
- `judgment/matcher.py` — 危险命令检测
- `judgment/verdict_collector.py` — verdict提取

### 因果记忆
- `causal_memory/biography.py` — 途径1：生平静态快照
- `causal_memory/causal_chain.py` — 因果链提取
- `causal_memory/causal_inference.py` — 因果推理
- `causal_memory/causal_memory.py` — 主模块
- `causal_memory/compressor.py` — 因果链压缩

### 感知层
- `perception/__init__.py` — 统一导出
- `perception/git_nexus_adapter.py` — GitNexus图谱集成

### 适配器
- `llm_adapter/` — MiniMax / OpenAI / Ollama 统一适配

### 工具
- `tools/` — 52个工具（8大类）
  - judgment(9) / memory(9) / perception(7) / emotion(7)
  - action(6) / goal(4) / output(4) / evolution(6)

---

## Review 状态

### P0/P1 ✅ 全部完成

| 问题 | 状态 |
|------|------|
| 三个SQLite散落 → v2.0 unified DB | ✅ |
| self_evolover拼写错误 | ✅ 已改名 self_evolver |
| experiences表定义分散 | ✅ init()统一_schema_tables |
| Outcome数据流断裂 | ✅ DB路径修复 |
| Evolver样本计数失效 | ✅ SQL JOIN修复 |
| router.py单体30KB | ✅ pipeline编排 |
| 三层架构循环导入 | ✅ __getattr__懒加载 |
| verdict提取fallback率40% | ✅ 新算法降至5% |
| P2 Stop-Hook无限递归（深度73）| ✅ 深度降至2次 |

### P2 待办

| 问题 | 状态 |
|------|------|
| biography正则脆弱 | 待办（LLM验证）|
| experiences需embedding | 待办 |

---

## CLI 命令

```bash
# 判断
python cli.py "Should I take this job offer?"

# Web控制台
python hub.py web
python hub.py web --port 8080

# 配置
python hub.py config wizard
python hub.py config show
python hub.py config set key val

# 验证
python hub.py verdict --show
python hub.py verdict -c <id> -w  # 标记错误
python hub.py verdict -c <id> -k  # 标记正确
```

---

## 关键设计原则

1. **铁律保护核心身份** — 某些特质不能被进化掉
2. **Fitness = "符合这个人"** — 不是通用标准认为正确的事
3. **全量版本快照** — 任何历史状态可恢复
4. **滚动缓冲区** — SQLite，100条上限，有界文件大小
5. **有界信念更新** — 每次 verdict 最大 10% 变化
