# gstack 集成文档 - 聚活

本模块逆向集成了 [garrytan/gstack](https://github.com/garrytan/gstack) 的核心设计，为聚活数字分身带来完整的**虚拟工程团队 workflow**。

## 核心价值

gstack 的核心洞察：**一个人可以像一个 23 人团队一样工作** —— 通过角色分工，每个角色专注一件事，流程化覆盖完整开发周期。

对于聚活（个人数字分身）来说，gstack 提供了：

1. **完整角色分工** —— 23 个专家角色（CEO/产品/架构/设计/安全/QA/发布等）
2. **标准化流程** —— Think → Plan → Build → Review → Test → Ship → Reflect
3. **持久化浏览器架构** —— 长生命周期 Chromium daemon，保持登录状态，亚 100ms 命令响应

## 使用示例

### 创建一个完整的 gstack 工作流

```python
import sys
sys.path.insert(0, ".")
from juhuo import (
    create_gstack_workflow,
    GStackWorkflow,
)

# 创建工作流
wf = create_gstack_workflow(
    project_name="my-new-feature",
    initial_idea="我要做一个个人每日简报小程序，整合日历和天气",
    llm_config={
        "provider": "minimax",
        "api_key": "YOUR_API_KEY",
        "model": "xxxxx",
    }
)

# 运行完整自动规划 (office-hours → ceo → design → eng)
tasks = wf.run_autoplan(
    is_user_facing=True,
    is_developer_facing=False,
)

# 获取完整计划
plan = wf.get_full_plan()
print(plan)

# 保存工作流状态
wf.save_workflow("gstack-workflow.json")
```

### 分步手动执行

```python
# 1. Office Hours - 产品问诊
task1 = wf.run_office_hours()

# 2. CEO Review - 范围和产品定位
task2 = wf.run_ceo_review()

# 3. 可选: Design Review (如果用户-facing)
task3 = wf.run_design_review()

# 4. 可选: DevEx Review (如果是 SDK/API/CLI)
task4 = wf.run_devex_review()

# 5. Engineering Review - 架构设计
task5 = wf.run_eng_review()

# 进入 Build 阶段...
```

### 使用浏览器 Daemon 做自动化 QA

```python
from juhuo import BrowserDaemonClient, GStackBrowserQA

# 连接到已启动的 daemon
client = BrowserDaemonClient()
port = client.ensure_running()
print(f"Browser daemon running on port {port}")

# 测试用户流程
result = client.test_flow(
    base_url="https://staging.myapp.com",
    steps=[
        {"action": "goto", "url": "https://staging.myapp.com/login"},
        {"action": "snapshot"},  # 获取 refs
        {"action": "fill", "ref": "@e1", "text": "test@example.com"},
        {"action": "fill", "ref": "@e2", "text": "password"},
        {"action": "click", "ref": "@e3"},
        {"action": "screenshot", "path": "login-result.png"},
    ]
)

print(f"Test {'passed' if result['success'] else 'failed'}")
print(f"Errors: {result['errors']}")
```

## 角色列表

| Role | Title | 用途 |
|------|-------|------|
| `office-hours` | YC Office Hours | 新产品问诊，六个问题重构问题 |
| `plan-ceo-review` | CEO / Founder Review | 范围挑战，产品定位，找到 10 星产品 |
| `plan-eng-review` | Engineering Manager | 架构锁定，数据流，边界用例，测试策略 |
| `plan-design-review` | Senior Designer | 设计维度评分，AI slop 检测 |
| `plan-devex-review` | Developer Experience Lead | DX 审核，开发者对时间分析 |
| `design-consultation` | Design Partner | 从零构建完整设计系统 |
| `design-review` | Designer Who Codes | 设计审核 + 修复 |
| `devex-review` | DX Tester | 实际测试开发体验 |
| `design-shotgun` | Design Explorer | 生成多个变体，视觉迭代 |
| `design-html` | Design Engineer | Mockup → 生产 HTML |
| `review` | Staff Engineer Code Review | 找生产环境 bug |
| `investigate` | Systematic Debugger | 根因调试，不猜测，三次失败停止 |
| `qa` | QA Lead | 真实浏览器测试，找 bug，自动修复 |
| `qa-only` | QA Reporter | 只报告不修复 |
| `cso` | Chief Security Officer | OWASP Top 10 + STRIDE 安全审计 |
| `ship` | Release Engineer | 同步，测试，推送，开 PR |
| `land-and-deploy` | Release Engineer | 合并，等待 CI，部署，验证生产 |
| `canary` | SRE | 部署后监控 |
| `benchmark` | Performance Engineer | 性能基准测试 |
| `document-release` | Technical Writer | 更新文档匹配代码 |
| `retro` | Engineering Manager | 每周回顾 |
| `autoplan` | Auto Plan Pipeline | 一键完整规划 (CEO → design → eng) |
| `learn` | Memory Manager | 管理跨会话学习 |

## 浏览器 Daemon 架构

借鉴 gstack 核心架构：

```
Claude / 聚活                  gstack
─────────                   ──────
                               ┌──────────────────────┐
  Tool call: snapshot -i    │  CLI (compiled binary)│
  ─────────────────────────→   │  • reads state file   │
                               │  • POST /command      │
                               │    to localhost:PORT   │
                               └──────────┬───────────┘
                                          │ HTTP
                               ┌──────────▼───────────┐
                               │  Server (Bun.serve)   │
                               │  • dispatches command  │
                               │  • talks to Chromium   │
                               │  • returns plain text  │
                               └──────────┬───────────┘
                                          │ CDP
                               ┌──────────▼───────────┐
                               │  Chromium (headless)   │
                               │  • persistent tabs     │
                               │  • cookies carry over  │
                               │  • 30min idle timeout  │
                               └───────────────────────┘
```

**设计要点：**

- **持久化状态** — 登录一次保持登录，cookie/tab 都保留
- **亚秒级响应** — 首次启动 ~3s，之后每次命令 ~100-200ms
- **ref 寻址** — 基于可访问性树，不修改 DOM，兼容 CSP/React
- **安全** — localhost 只接受本地请求，Bearer token 认证

## 与 Hermes 主动闭环学习的关系

| 模块 | 用途 | 互补 |
|------|------|------|
| **gstack** | 完整 23 人虚拟团队角色分工，覆盖全流程 | 提供流程框架 |
| **Hermes** | 主动闭环自我进化，从经验中持续学习 | 提供学习闭环 |
| **聚活** | 个人数字分身，融合两者，持续模拟个人决策 | 产品形态 |

gstack 提供了**分工流程**，Hermes 提供了**自我改进机制**，两者结合就是完整的个人数字分身：

```
gstack 分工 → 产出工作 → Hermes 学习反馈 → 聚活进化 → 下次 gstack 更准
```

## 依赖

- 如果只需要工作流：Python + 聚活已有的 `llm_adapter` 即可
- 如果需要浏览器 QA：需要先安装 gstack 原生浏览器 daemon：

```bash
git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

聚活的 Python 客户端会自动连接到已安装的 daemon。

## License

gstack 本身是 MIT 许可证，本集成遵循原许可。
