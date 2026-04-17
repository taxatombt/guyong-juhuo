# Changelog

All notable changes to this project will be documented in this file.

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
