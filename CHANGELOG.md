# Changelog

All notable changes to this project will be documented in this file.

## [2.2.1] - 2026-04-24

### Added
- **Hermes Guide P0 落地** — 16册白皮书啃读落地
  - **JudgmentBudget**（`judgment/judgment_budget.py`）：栈深度+verdict数+超时三重保护，防止递归
  - 集成到 `subsystems/judgment/closed_loop.py`：`receive_verdict` 入口增加 `budget.enter()` + `try/except BudgetExceeded`
  - **FTS5全文索引**（`experiences.py`）：SQLite FTS5 bm25 排序 + 3个同步触发器（AI/AD/AU）
  - `fts_search()`：FTS5 主搜索，bm25 排名
  - `find_similar()`：FTS5-primary + keyword fallback 去重合并（无重复）

### Fixed
- **P2 Stop-Hook 无限递归** — `receive_verdict` → `stop_hook.capture_verdict` → `receive_verdict` 死循环
  - 根因：`judgment_snapshots` 查询缺 `corrected` 防护，递归时重建 `target` 导致再次触发 hook
  - 修复：`_snap_corrected != 1` 时才重建 target，避免 corrected=1 时重复触发
  - 结果：递归深度 73→2 层，`max_depth` 285→18，20 verdict 从 >120s → ~20s

- **信念更新验证** — `receive_verdict` → `update_dimension_beliefs` 端到端验证通过
  - 修复后 10/10 维度 hit_count 正确增加

- **Self-Evolver 触发** — evolver 正常触发，`winner=old`，无假 100% 改善

### Added
- **CLI 交互反馈入口** — `cli.py` judge 后提示用户 y/n/u 标记判断质量
  - y: 正确，n: 错误，u: 不知道
  - 自动调用 `receive_verdict` / `receive_actual_choice`

### Chores
- 移除 `get_dimension_beliefs` 残留 debug 代码（`chain_id` 未定义 NameError）
- 移除 117 个 `_*` / `debug_*` 临时文件
- `emotions.json` 格式修复（553 条记录，wrap 为 `{"signals": [...]}` 格式）

## [2.2] - 2026-04-23

### Added
- **Lessons System v2** — 因果链教训层（P2-1/P2-2/P2-3全部完成）
  - `judgment/lessons.py` — 完整教训系统（326行）
  - **P2-1 LLM语义提取**: `_llm_extract_lessons()` — MiniMax API调用 + fallback规则提取
  - **P2-2 50条种子教训**: 9领域49条种子，investment(13)/career(8)/relationship(6)/health(6)/universal(3)/family(4)/finance(4)/education(3)/migration(3)
  - **P2-3 Confidence时间衰减**: 半衰期30天，`exp(-ln2 * days_elapsed / 30)`，有效置信度 = stored × decay
  - `lessons_to_prompt()` → router.py `_build_answer_prompt(lessons_context=...)` → 第5位注入
  - 20列表schema: `id, lesson_type, domain, pattern, root_cause, correction, positive_cases, negative_cases, hit_count, miss_count, confidence, source, tags, verified, instance_signature, created_at, updated_at, last_reinforced, times_applied, user_id`

### Fixed
- Schema不匹配: `LESSONS_SCHEMA`从12列→20列，与表定义对齐
- Cursor vs Connection: `c.lastrowid` → `cur.lastrowid`
- `SELECT *` 列错位: DROP旧表→重建→INSERT seeds
- DB路径: lessons.py 用 `E:\juhuo\data\judgment_data\juhuo.db`

## [2.0] - 2026-04-22

### Added
- **UnifiedProfile 单汇聚层** — L1(facts) + L2(patterns) + L3(intents) → `ProfileEntry` 统一结构
  - `judgment/user_model.py` — `UserModel.generate()` / `to_prompt()` / `to_summary()`
  - `inject_unified_profile()` — pipeline 唯一汇聚点（移除三个旧 injector）
  - `ProfileEntry` dataclass: `source/fact/pattern/signal`, `priority(1/2/3)`, `dimension`, `claim`, `recency_score`, `contradiction_flag`
  - 端到端：37 profile entries / 552 chars unified_context

- **三路优先级铁律**：experiences(做的) > biography(说的) > behavior(被动追踪的)
  - L2 experiences: `find_similar_structured()` — `similarity(0.6) + keyword_overlap(0.4)` 融合权重
  - L1 biography: 分级半衰期 per-item `half_life_days`（`biographical_facts` 表新列）
  - L2 behavior: `_get_l3_behaviors()` → `BehaviorEntry` dataclass → 合并进 L3 intents

- **P1 矛盾双向检测** — L1 声称 vs L2 行为 → 双向调整权重
  - `generate()`: L1 降 `priority=3`（降级），L2 升 `priority=1`（升级），`contradiction_flag=True` 双向
  - `to_prompt()`: 结构化格式 `[PROFILE: priority=X, source=Y, recency=Z, claim="...", flag=Z]`

### Fixed
- **pipeline.py 死代码清理** — `inject_biography`/`inject_experiences`/`inject_causal_memory` 定义删除，325→265行
- **perception_intents 表路径** — `_pi_db == _juhuo_db` 确认，`perception_intents` 在 `data/juhuo.db`

### Changed
- **Experiences embedding v1** — MiniMax `embo-01` 向量 + cosine similarity 混合检索
- **biography.py 增强** — 26条正则扩展（年龄近似/职业/家庭/学历），`confidence` 字段 per-item
- **life_os.py PAD 扩展** — 情绪词 6→30+，PAD阈值修复（anxiety/excitement/anger 区分）

---

## [2.0] - 2026-04-21

### Added
- **三途径信息层** — 真正的判断依据是价值观+经历+直觉
  - `judgment/biography.py`: 生平事实层（P1），26条正则，8类：年龄/职业/家庭/财务/所在地/健康/价值观/学历
  - `judgment/exiences.py`: 经历层（v1），20条冷启动种子，判断偏好历史
  - `judgment/behavior_logger.py`: 行为日志层（P2），8个 ActionChannel，工具调用链
  - router.py 集成：biography 自动抽取+注入，experiences 查询+存储，behavior 记录
  - cli.py 新增：`bio show/add/list`、`behavior stats/list/show` 命令

- **Life OS v3** — 精力/情绪驱动的任务调度
  - `life_os.py` 完全重建：`_juhuo_rank()` 直接调用 MiniMax adapter（单 prompt，绕过 10 维 pipeline 超时）
  - 两模式：`--juhuo` 调用 LLM 排序，`--juhuo` 时 API 超载 fallback 到 60% 均分
  - verdict 解析：从 `排序:[1,2,...]` 提取排名映射置信度（第1名=100%，第2名=85%...）
  - MiniMax `<think>` 块太长导致正文为空：手动 `re.sub(r"<think>.*?</think>","",...)` 提取

- **experiences layer v1** — 判断偏好历史存储
  - `experiences` 表：`user_id` 隔离，`situation_type` 9类，`task_hash` 防重复
  - `find_similar()`: sliding window 中文 bigram 关键词提取 + substring 匹配
  - `get_context_for_judgment()`: 历史相似判断作为 prompt 上下文注入
  - 20 条 EXPERIENCE_SEEDS 冷启动数据

### Fixed
- `judgment/router.py`: 删除本地影子 `_answer_questions`（与 `llm_calls.py` 不同步），委托 canonical 版本
- `judgment/llm_calls.py`: 补全缺失 `get_adapter`/`CompletionRequest` import
- experiences bug：`全仓进股市` 被贪心切词切断 → sliding window 方案
- experiences bug：`type_bonus=0` → 加 `["股市","全仓"]` 到 investment 类型

### Changed
- `_answer_questions` 超时问题：轻量化绕道——`_juhuo_rank()` 直接 adapter call，不走完整 check10d pipeline
- MiniMax `disable_thinking=True` 无效：prompt 很长时 `<reasoning>` 块占满 output token，正文为空 → 手动后处理

---

## [1.9] - 2026-04-18

### Added
- **ActionExecutor** — 三通道执行层（action_system/action_executor.py, 260行）
  - `execute_via_benchmark()`: GDPVal ground truth 对比验证
  - `execute_via_hermes()`: copaw agents chat → 本地 Hermes agent
  - `execute_via_claude_code()`: claude/codex CLI 委托编程任务
  - `get_execution_history()` / `get_channel_stats()`: 执行历史查询
  - `_verify_and_feedback()`: 执行结果自动写 outcome_predictions
- **check10d_and_execute()** — 判断→执行→验证→进化 一体入口
- **Outcome Prediction + Verification 层** (closed_loop.py, 270行)
  - 新表 `outcome_predictions`: predicted/actual action+consequence+score
  - `predict_outcome()`: snapshot时自动从verdict提取推荐行动
  - `verify_outcome()`: 事后验证，自动计算 outcome_score
  - `get_verification_stats()`: 全局准确率+各维度弱项
  - `auto_predict_from_verdict()`: verdict文本智能提取
- **judgment_snapshots.verdict** 字段: ALTER TABLE 迁移
- **receive_verdict()** 新参数: actual_action, actual_consequence, outcome_score, verifier

### Fixed
- **benchmark._calc_match** — 修复 match=0 问题
  - 删除 `_SYNONYMS` 死代码（关键词簇分类冲突）
  - 主题重叠自动检测（≥3个2gram共享→同话题）
  - n-gram 子串匹配替代 difflib（对中文无效）
  - 11/11 mock cases PASS
- **snapshot_judgment** — 传入 verdict 字段（router.py）
- **闭环数据断** — check10d_run → snapshot_judgment → receive_verdict 链路修复

## [1.8] - 2026-04-18

### Added
- InsightTracker 完整实现（token/cost/verdict追踪）
- ContextFence 围栏包装（prompt injection 防御）
- Verdict 自动积累（verdict="pending"）
- Self-Evolver 验证闭环
- README TODO 清单

### Legacy Cleanup
-因果记忆选型 JSONL 主力，SQLite 归档 __trash__/
- .gitignore 新增 __trash__/

## [1.7] - 2026-04-17

### Fixed
- **Self-Evolver Rollback** — `_rollback_self_model()` 重写，修复不存在函数引用
  - 去掉了不存在的 `_model_to_dict`/`_dict_to_model` 依赖
  - 改用 `evolved_weights.json` history 恢复到上一组权重
  - fallback 到 `shutil.copy2` 备份恢复
- **EvolverScheduler** — 内存+SQLite 双追踪系统合并为 SQLite 单一事实来源
  - `record_outcome()` → 委托 `add_verdict_to_evolution_tracking()`
  - `validate_evolution()` → 委托 `verify_evolution()`
  - `apply_evolved_weights()` → 同时调用 `register_evolution()`

### Changed
- **方向收拢** — Self-Evolver 目标降级为「维度权重闭环」（不做系统自动变强）
- **HRR** — 移除自研计划，改为监控触发条件（500条/100ms）
- **因果记忆** — JSONL 主力，SQLite 废弃归档 `__trash__/`

### Added
- **judgment/seed_verdicts.py** — 36条种子 verdicts（基准准确率 63.9%）
- **judgment/compactor.py** — Context 压缩器（Codex启发，8000token触发）

## [1.6] - 2026-04-17

### Added
- **judgment/config.py** — 集中生产配置（BIAS=3, MIN=5, COOLDOWN=24h）
- **GDPVal Benchmark** — 22案例 + 语义匹配 + A/B/C/D 评分
- **verdict_collector** — `import_from_judgment_db()` 从 snapshots 种子导入
- **judgment/logging_config.py** — 统一日志配置

### Fixed
- **Self-Evolver 验证闭环** — `apply_evolved_weights()` → `start_evolution_tracking()`
- **EvolverScheduler 启动** — `router.py` 初始化时自动启动

## [1.5.2] - 2026-04-17

### Added

#### Core Features
- **十维判断 (Judgment)** — 23个模块的完整判断系统
- **闭环进化** — 判断 → 记录 → 反馈 → 进化
- **Self-Evolver** — 自动识别模式，写入规则，防止下次犯错
- **Skill Evolver** — 追踪成功率，调整触发条件
- **Benchmark** — 8案例测试集，维度准确率评估

#### Claude Code 启发
- `verification_agent.py` — 独立验证 Agent，三级验证
- `tool_governance.py` — 14步工具治理 Pipeline
- `compactor_v2.py` — 四道压缩 (Snip/Micro/Collapse/Auto)

#### OpenClaw 启发
- `skill_loader.py` — Skills 按需加载（metadata 注入）
- `openclaw_hooks.py` — 17个 Hook 事件节点
- `session.py` — Agent Loop 生命周期管理

#### QwenPaw 启发
- `rate_limiter.py` — LLM 限流 (QPM/并发/Backoff)
- `config/env_loader.py` — 类型安全配置

#### CLI & Web
- `web_console.py` — Flask Web Console (端口 18768)
- `cli.py` — 完整 CLI (10个子命令)
- `mcp_server.py` — MCP Server 工具
- `i18n.py` — 多语言支持 (zh_CN/en_US)
- `self_test.py` — 6项启动自检

#### Infrastructure
- `Dockerfile` — Docker 镜像
- `docker-compose.yml` — 容器编排

### CLI Commands

```bash
juhuo [task]       # 单次判断
juhuo shell        # 交互模式
juhuo web          # Web Console
juhuo status       # 状态查看
juhuo verdict      # verdict 管理
juhuo config       # 配置管理
juhuo test         # 自检
juhuo benchmark    # 测试
```

### Architecture

```
juhuo/
├── judgment/          # 十维判断（23个.py）
│   ├── pipeline.py    # 完整流水线
│   ├── dynamic_weights.py  # 动态权重
│   ├── benchmark.py   # 质量评估
│   ├── self_test.py   # 自检
│   ├── verification_agent.py
│   ├── tool_governance.py
│   ├── compactor_v2.py
│   ├── openclaw_hooks.py
│   └── session.py
├── causal_memory/     # 因果记忆
├── self_model/        # 自我模型
├── skills/           # Skills 自进化
├── llm_adapter/      # LLM 适配器 + 限流
├── config/           # 配置系统
├── tools/            # 52个工具
├── web_console.py    # Web 界面
├── cli.py            # CLI
├── mcp_server.py     # MCP
└── i18n.py           # 国际化
```

## [1.5.1] - 2026-04-16

### Added
- Tools 系统 (52个工具)
- MCP 集成
- CI/CD 测试

## [1.5.0] - 2026-04-16

### Added
- Self-Evolver 完整闭环
- 4类记忆系统
- Skill 系统
- Loguru 日志

## [1.0.0] - 2026-04-14

### Added
- Initial release
- 10维判断框架
- 因果记忆
- 自我模型

---

---

## [2.2.2] - 2026-04-25

### Added
- **Self-Verification Loop** — Anthropic Building Effective AI Agents 第7条铁律落地
  - `_verify_judgment()` in `judgment/llm_calls.py`：无额外LLM调用的轻量矛盾检测
  - 两步关键词方向检测（pro/con/neutral），negated_positions防双重计算
  - 15对预设矛盾维度检测（cognitive×emotional/economic等）
  - verification_score综合评分 + low_quality_verdict标记
  - 集成到 `judgment/router.py` 的 `check10d_run()`

_Last updated: 2026-04-25_
