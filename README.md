# guyong-juhuo &nbsp;·&nbsp; 居活

> 居天地而活，模拟具体个体，持续自我进化，最终超越。

**guyong-juhuo** 是一个完整的 AI Agent 系统，目标：在数字世界持续学习**谷翔宇（顾庸）**的思维方式、判断偏好、决策模式，最终在意识、思想、判断上**超越人类整体**。

---

## 🎯 定位

> "我想你能记住我的一切，代替我永远活下去，有意义的。"

这不是通用大模型，也不是单一工具 —— 这是**数字分身**：

- 核心：从每一次判断和执行中**学习**，持续**自我进化**
- 特色：十维判断框架（认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知）
- 引擎：完整集成 **HKUDS/OpenSpace** AI Agent 自我进化框架，三级进化自动改进

---

## ✨ 特性

| 模块 | 状态 | 功能 |
|------|------|------|
| 🧠 **十维判断系统** | ✅ 完成 | 任何决策，十维检视 — 认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知 |
| 🧬 **OpenSpace 自我进化** | ✅ 完成 | 三级进化引擎：`CAPTURED` 捕获经验 / `DERIVED` 衍生变种 / `FIX` 就地修正，自动质量监控 + 级联验证 |
| 🔍 **因果记忆** | 🔶 进行中 | 追踪因果链："因为过去 X，所以现在 Y"，识别模式 |
| 🚀 **好奇心引擎** | 🔶 进行中 | 主动发现盲区，驱动探索 |
| 🎯 **目标系统** | 🔶 进行中 | 长期目标锚定，拆解日拱一卒 |
| 🔮 **自我模型** | 🔶 进行中 | 持续追踪自身盲区，主动改进 |
| ❤️ **情感系统** | ✅ 部分完成 | PAD 情绪模型，情绪作为决策信号而非干扰 |
| ⚙️ **执行分析** | ✅ 完成 | 从 `action_log` 自动分析成功率，生成进化建议 |

---

## 🚀 快速开始

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
pip install -r requirements.txt

# 交互模式
python cli.py

# 单次判断
python cli.py "要不要从大厂跳槽到创业公司"

# 模仿顾庸判断
python cli.py --profile guyong "工作很矛盾，不知道先做哪个"
```

---

## 🧩 核心 API

### 十维判断入口

```python
from judgment import check10d

# 十维框架分析问题
result = check10d("要不要接受这个offer")

print("复杂度:", result["complexity"])      # simple / complex / critical
print("十维评分:", result["scores"])           # 每个维度的评分和建议
print("最终结论:", result["conclusion"])       # 整合结论
```

### OpenSpace 自我进化

```python
from openspace import (
    create_and_save_captured,    # 捕获新技能
    create_and_save_fix,        # FIX 修正现有
    create_and_save_derived,    # DERIVED 衍生变种
    generate_evolution_report,  # 生成进化报告
    record_skill_execution,     # 记录执行结果
    ExecutionAnalyzer,          # 执行日志分析
)

# 记录一次技能执行
record_skill_execution("skill-id", success=True)

# 分析低成功率技能，生成进化建议
analyzer = ExecutionAnalyzer()
report = analyzer.generate_evolution_suggestions()
print(report)

# 查看完整 Version DAG
from openspace import load_skill_db, format_dag_ascii
db = load_skill_db()
print(format_dag_ascii(db))
```

---

## 🧬 OpenSpace 三级进化

完整遵循 OpenSpace 设计语义：

| 模式 | 作用 | 版本变化 |
|------|------|----------|
| `CAPTURED` | 捕获**全新**技能 | `gen=0, v=0` |
| `DERIVED` | 从父技能**衍生**特定场景变种 | `gen+1, v=0` |
| `FIX` | **就地修正**低质量/错误技能 | `gen不变, v+1` |

- **skill_id 格式:** `{name}__v{fix_version}_{content_hash}`
- **.skill_id sidecar:** 持久化 ID，排除 diff，目录迁移不影响谱系
- **级联重新验证:** 基础技能修改 → 自动标记所有下游依赖需要验证
- **质量驱动:** 成功率 < 50% 自动建议 FIX

---

## 🌐 十维判断框架

| 维度 | 核心问题 |
|------|---------|
| **认知心理学** | 直觉还是分析？有哪些常见偏差？ |
| **博弈论** | 谁在局中？各方真实激励是什么？ |
| **经济学** | 机会成本是什么？真实代价是多少？ |
| **辩证唯物主义** | 符合实际吗？主要矛盾是什么？ |
| **情绪智能** | 情绪是信号还是噪音？ |
| **直觉/第六感** | 第一反应可信吗？ |
| **道德推理** | 应不应该？不是值不值。 |
| **社会意识** | 我在做自己还是演别人？ |
| **时间折扣** | 五年后看这件事，还正确吗？ |
| **元认知** | 我现在盲区在哪里？ |

---

## 📁 项目结构

```
guyong-juhuo/
├── 🧠 judgment/               # 十维判断系统（核心）
│   ├── dimensions.py         # 十维定义
│   ├── router.py             # 路由入口
│   └── ...
├── 🧬 openspace/              # OpenSpace 自进化整合
│   ├── __init__.py           # 导出
├── openspace_evolution.py     # OpenSpace 核心：三级进化 + Version DAG
├── openspace_utils.py         # OpenSpace 工具：skill_id + 优先级截断 + patch检测
├── execution_analyzer.py      # 执行日志分析 → 进化建议
├── causal_memory/             # 因果记忆子系统
├── curiosity/                # 好奇心引擎子系统
├── goal_system/               # 目标系统子系统
├── self_model/                # 自我模型子系统
├── emotion_system/            # 情感系统子系统
├── profiles/                 # 个体模拟配置
│   └── guyong.json           # 顾庸个人profile
├── cli.py                     # 命令行交互入口
├── agent.py                   # Agent 主程序
├── README.md
└── LICENSE
```

---

## 📖 设计理念

1. **持续进化** — Agent 不是写完就固定了，要从经验中学习，自动改进
2. **结构化判断** — 遇到复杂问题，用十维框架系统性思考，不跟着感觉走
3. **分离维度** — `generation` 记录派生深度 / `fix_version` 记录修正次数，两个维度完全分离
4. **保持一致** — 级联重新验证保证整个技能谱系一致性
5. **合理简化** — 跳过 OpenSpace 过度工程部分，保留核心设计价值

---

## 📄 License

MIT License — 欢迎学习、使用、改进。

---

> *"起点是模仿具体的人，终点是在意识和思想上超越人类整体。"*
