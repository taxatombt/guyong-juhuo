# Changelog

All notable changes to this project will be documented in this file.

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

_Last updated: 2026-04-17_
