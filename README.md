# guyong-juhuo · 聚活

<p align="center">
  <img src="logo.svg" width="320" alt="juhuo logo">
</p>

**一个会进化的个人数字分身。**

模拟特定个体的思维方式，在判断力上超越人类整体。

> 🌍 **English version:** [README_en.md](README_en.md)

---

## 目录结构

```
juhuo/
│
├── judgment/          # 十维判断系统
│   ├── router.py             # 入口：路由到对应维度
│   ├── dimensions.py          # 十维定义
│   ├── judgment_rules.py      # 十维规则引擎（P3）
│   ├── fitness_evolution.py   # Fitness反馈循环
│   ├── verifier.py            # 判断验证器
│   ├── closed_loop.py         # SQLite持久化
│   ├── judgment_db.py         # 数据库层
│   ├── stop_hook.py           # Stop事件捕获
│   ├── context_fence.py       # 上下文围栏
│   ├── life_cycle_hooks.py    # 11个生命周期钩子
│   ├── protocol.py            # ExitCode协议
│   ├── matcher.py             # 危险命令检测
│   └── pre_tool_hook.py       # PreToolUse/PostToolUse钩子
│
├── causal_memory/     # 因果记忆
│   ├── causal_memory.py       # 快慢双流架构
│   ├── causal_inference.py    # 因果推断引擎（P0）
│   ├── causal_chain.py        # 跨事件因果链
│   ├── compressor.py          # 四道压缩+五阶段
│   └── types.py              # 因果事件类型
│
├── self_model/       # 自我模型
│   └── self_model.py          # 贝叶斯盲区追踪
│
├── curiosity/        # 好奇心引擎
│   ├── curiosity_engine.py    # 双随机游走
│   └── ralph_loop.py         # Ralph自引用循环
│
├── emotion_system/   # 情感系统
│   └── emotion_system.py     # PAD三维模型
│
├── feedback_system/  # 反馈系统
│   └── feedback_system.py
│
├── goal_system/      # 目标系统
│   └── goal_system.py        # 洋葱时间锚定
│
├── perception/       # 感知输入层
│   └── perception.py
│
├── output_system/    # 输出格式化
│   └── output_system.py
│
├── action_system/    # 行动规划
│   └── action_system.py
│
├── openspace/        # Skill进化系统
│   └── openspace.py
│
├── web/              # 网页控制台
│
├── docs/             # 架构文档
│
├── data/             # 数据持久化
│   └── judgment_data/
│       └── juhuo_judgment.db  # SQLite数据库
│
├── cli.py            # 命令行入口
├── tui_console.py   # TUI终端界面
├── profile.py        # 用户身份配置
├── config.py         # 全局配置
└── launcher.bat      # Windows启动器
```

---

## 核心能力

### 判断一个两难问题

```bash
python cli.py "我应该接受这个offer还是继续找?"
```

### 危险命令检测（Codex启发）

```python
from judgment.matcher import check_safe

blocked, reason = check_safe("rm -rf /")
# blocked=True, reason="递归强制删除（危险）"
```

### PreToolUse安全钩子

```python
from judgment.pre_tool_hook import pre_action_check

outcome = pre_action_check("execute", {}, "rm -rf /")
# action=BLOCK, should_block=True
```

### 11个生命周期钩子

```python
from judgment.life_cycle_hooks import (
    build_system_prompt,    # 会话开始
    prefetch_all,           # 每轮前召回
    sync_all,               # 每轮后写入
    on_turn_start,          # Turn开始
    on_turn_end,           # Turn结束
    on_pre_action,          # 动作前 (Codex)
    on_post_action,         # 动作后 (Codex)
    on_session_end,         # 会话结束
)
```

### 因果推断引擎

```python
from causal_memory.causal_inference import CausalInference

ci = CausalInference()
inference = ci.infer("用户抱怨速度慢", ["查询超时", "数据库负载高"])
```

### Fitness反馈循环

```python
from judgment.fitness_evolution import get_fitness_tracker

tracker = get_fitness_tracker()
tracker.record_judgment(task, dimensions, result)
fitness = tracker.get_fitness_score()
```

---

## 架构设计

```
judgment（判断）
    ↓
causal_memory（因果记忆）
    ↓
self_model（自我模型更新）
    ↓
下次判断改善（闭环）
```

### Codex Rust启发实现

| Codex特性 | Juhuo实现 |
|-----------|-----------|
| ExitCode协议 | `protocol.py` ExitCode枚举 |
| PreToolUse钩子 | `pre_tool_hook.py` PreToolHook |
| PostToolUse钩子 | `pre_tool_hook.py` PostToolHook |
| Matcher模式 | `matcher.py` Matcher |
| Hook事件 | `life_cycle_hooks.py` 11个钩子 |

### Hermes启发实现

| Hermes特性 | Juhuo实现 |
|------------|-----------|
| 五阶段压缩 | `compressor.py` Prune→Protect→Summarize→Iterative |
| 上下文围栏 | `context_fence.py` |
| 9个生命周期钩子 | `life_cycle_hooks.py` |

---

## 两种判断模式

| 模式 | 说明 |
|------|------|
| **模仿模式** | 传入agent_profile，强制对齐特定个体的判断方式 |
| **超越模式** | 十维通用判断，在判断力上超越人类整体 |

---

## 铁律

> **模拟特定具体个体，最终在判断力上超越人类整体。**

---

## 安装

```bash
# Windows
launcher.bat              # 网页控制台
launcher.bat --tui       # TUI终端

# 或直接运行
python cli.py "你的问题"
```

---

## 版本

当前版本：v1.3（2026-04-16）

详见 [CHANGELOG.md](CHANGELOG.md)