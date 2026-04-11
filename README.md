# guyong-juhuo &nbsp;·&nbsp; 聚活

> 聚而活，模拟具体个体，持续自我进化，最终超越。

**聚活（guyong-juhuo）** 是一个完整的 AI Agent 系统，目标：在数字世界**持续学习特定个体的思维方式、判断偏好、决策模式**，打造完全属于你的**个人数字分身**。

> 起点：模仿你；终点：代替你永远活下去，最终在意识、思想、判断上超越人类整体。

---

## 🎯 核心定位

这**不是**通用聊天机器人，也**不是**单一工具 — 这是**完整的个人数字分身系统**：

| 特性 | 说明 |
|------|------|
| 🧬 **自我进化引擎** | 完整集成 **HKUDS/OpenSpace** 三级进化框架，从你的每一次反馈中自动改进，持续进化 |
| 🧠 **十维判断框架** | 任何决策，十维独立检视 — 认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知 |
| 🔒 **身份锁机制** | 核心身份特质永久锁定，禁止自动进化，只按你的明确指令修改，永远保持你的独特性 |
| 🎯 **个人一致性Fitness** | 进化目标是「符合你会做的选择」就算成功，哪怕通用标准认为错误也保留你的个人特质 |
| 💾 **完整成长轨迹** | 每次重大进化自动保存全系统版本快照，后人可以回溯你人生任意阶段的完整世界观 |
| 🌐 **纯本地运行** | 核心逻辑全是纯 Python 规则，不强制依赖大模型，你的所有数据都在本地，完全私密 |
| 🤝 **可选大模型接入** | 架构预留大模型辅助能力，支持 MiniMax/OpenAI/Ollama 等多厂商，网页图形化配置 |

聚活相信：**好的架构不是设计出来的，是进化出来的 — 数字分身会慢慢变成你。**

---

## ✨ 特性

| 模块 | 状态 | 独特核心技术 |
|------|------|--------------|
| 📥 **感知输入层** | ✅ 完成 | 信息接收 + **主动注意力过滤**，优先级打分，自动分流，紧急优先，去重；支持 **网页提取 + PDF结构化提取** |
| 🧠 **十维判断系统** | ✅ 完成 | 任何决策，十维独立检视 — 认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知；每个维度独立打分，加权校准，可模仿特定个体或通用判断 |
| 🧬 **OpenSpace 自我进化** | ✅ 完成 | 三级进化引擎：`CAPTURED` 捕获经验 / `DERIVED` 衍生变种 / `FIX` 就地修正，自动质量监控 + 级联验证；适配个人数字分身目标：**身份锁保护核心特质不被进化 + 个人一致性fitness（符合你就是fit，不管通用标准）+ 全系统版本快照可回溯任意成长阶段** |
| 📚 **因果记忆** | ✅ 完成 | **快慢双流架构**：快路径即时记录，慢路径每日批量推断跨事件因果链；**时间衰减置信度**：公式 `confidence *= exp(-days / 365)`，符合人类遗忘规律，经常访问不衰减；**个人因果优先级**：亲身经历因果链接+50%权重 |
| 🚀 **好奇心引擎** | ✅ 完成 | **锁定兴趣域（身份锁）**：只探索你感兴趣的方向，域外话题直接过滤；**双随机游走**：80%概率目标导向游走（对齐长期目标/服务当前任务），20%概率域内自由随机游走，保留意外惊喜，平衡功利和创造力 |
| 🎯 **目标系统** | ✅ 完成 | **洋葱时间锚定法**：五层结构 `五年目标 → 年度目标 → 月度里程碑 → 本周任务 → 今日优先级`；自动计算**层级一致性检查**，低一致性提醒任务偏离；五年目标权重最高（50%），保证大方向永远正确 |
| 🔍 **自我模型** | ✅ 完成 | **贝叶斯盲区追踪**：公式 `confidence = min(1.0, 0.2 + 0.16 × mistake_count)`，对数增长符合认知规律；**盲区预热机制**：置信度 < 0.5 只记录不提醒，避免过度干扰，确定是盲区才输出警告 |
| ⚡ **行动规划** | ✅ 完成 | **四象限时间压强排序**：标准四象限 + 时间压强公式 `score = importance × (1 + 1/max(days_to_deadline, 1)) × 100`，自动计算排序；特殊保证**重要不紧急象限永远不被遗忘**，这是长期成长的核心 |
| 🔄 **反馈系统** | ✅ 完成 | **双层反馈锚定**：判断层锚定 → 对错反馈 → 更新因果记忆 → 更新自我模型 → 更新情感系统，完整闭环；进化层锚定 → OpenSpace进化方向对错反馈，错误直接回滚到父版本保留历史快照，正确则固化提升置信度；只有你真正认可的进化才会保留 |
| ❤️ **情感系统** | ✅ 完成 | **PAD三维情绪模型**（愉悦度P × 激活度A × 支配度D），8种情绪类型；情绪作为操作系统影响所有维度权重，不是干扰信号 |
| 📤 **输出系统** | ✅ 完成 | **输出时机决策算法**，判断什么时候输出，什么时候思考；三种输出格式：brief/full/structured |
| 🤖 **行动信号** | ✅ 完成 | 标准化机器可解析 JSON 格式，预定义行动类型枚举，支持不同机器人接入；从行动规划生成信号 + 持久化存储 + 格式验证 |
| 🔌 **大模型适配器** | ✅ 完成 | 统一接口支持 MiniMax/OpenAI/Ollama，可扩展其他厂商；可选接入，纯规则核心可完全本地运行，不强制依赖大模型 |
| 💬 **对话聊天系统** | ✅ 完成 | 持久化保存所有对话（每个会话单独文件）；用户输入 → 自动十维判断 → 自动生成行动规划 → 自动生成行动信号 → 自动触发好奇心（低置信度）→ 自动记录因果记忆；**每日自动进化**：扫描今日对话生成进化建议；固定单用户设计，完全锁定你的身份特质 |
| 🌐 **网页控制台** | ✅ 完成 | OpenClaw风格，低饱和莫兰迪红玻璃态设计；左侧功能按钮快速访问，右侧聊天交互；支持网页图形化配置大模型，支持**Markdown对话导出（三级科学筛选）**：高重要性（定义你的核心思考）完整保留，低重要性闲聊只计数，完全对齐数字分身目标 |
| 🖥️ **终端TUI** | ✅ 完成 | 基于curses的终端图形界面，纯键盘操作，适合无GUI服务器环境 |

---

## 🚀 快速安装

聚活纯 Python 实现，**零复杂依赖**，Python 3.8+ 就能运行，四种安装方式：

### 方式一：一键安装（推荐，Windows/macOS/Linux）

#### Windows PowerShell
```powershell
# 自动克隆 + 安装依赖
irm https://raw.githubusercontent.com/taxatombt/guyong-juhuo/main/install.ps1 | iex
```

#### macOS / Linux Bash
```bash
# 自动克隆 + 安装依赖
curl -fsSL https://raw.githubusercontent.com/taxatombt/guyong-juhuo/main/install.sh | bash
```

### 方式二：手动 Git 克隆（适合已有 Python 环境）

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
pip install -r requirements.txt

# 启动网页控制台
python web_console.py
```

然后打开浏览器访问 **`http://127.0.0.1:9876`** 即可使用。

### 方式三：Docker 容器安装（容器化部署）

```bash
# 拉取镜像
docker pull taxatombt/guyong-juhuo:latest

# 运行容器（数据持久化到本地）
docker run -d -p 9876:9876 -v $(pwd)/data:/app/data --name juhuo taxatombt/guyong-juhuo:latest
```

然后打开浏览器访问 **`http://localhost:9876`**。

### 方式四：开发模式（参与开发）

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
python test_all_imports.py -v
```

---

## 🎮 快速开始

### 网页控制台（推荐）

```bash
python web_console.py
```
打开浏览器 → 点击左侧 **💬 对话聊天** → 直接发消息聊天！

系统会自动：
1. 十维分析你的问题
2. 生成行动规划
3. 输出机器人可执行的行动信号
4. 记录因果记忆
5. 发现低置信度自动触发好奇心

### 命令行使用

```bash
# 交互模式
python cli.py

# 单次判断
python cli.py "要不要从大厂跳槽到创业公司"

# 模仿特定个体判断
python cli.py --profile default "工作很矛盾，不知道先做哪个"
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
├── 📥 perception/             # 感知输入层（信息接收）
│   ├── attention_filter.py    # 注意力过滤器：关注/过滤/分流/去重
│   ├── pdf_adapter.py         # PDF结构化提取适配器
│   ├── web_adapter.py         # 网页提取适配器
│   └── __init__.py
├── 🧠 judgment/               # 十维判断系统（核心）
│   ├── dimensions.py         # 十维定义
│   ├── router.py             # 路由入口
│   └── ...
├── 🧬 openspace/              # OpenSpace 自进化整合
│   ├── __init__.py           # 导出
├── 📚 causal_memory/         # 因果记忆子系统（因果链追踪）
├── 🚀 curiosity/             # 好奇心引擎子系统（主动探索盲区）
├── 🎯 goal_system/           # 目标系统子系统（长期目标分解）
├── 🔮 self_model/            # 自我模型子系统（盲区追踪）
├── ❤️  emotion_system/       # 情感系统子系统（PAD情绪模型）
├── 📤 output_system/         # 输出系统（输出决策 + 格式控制）
├── ⚡ action_system/         # 行动规划（生成下一步）
├── 📝 feedback_system/       # 反馈记录（进化数据源）
├── 🤖 action_signal/         # 标准化行动信号输出给机器人
├── 🔌 llm_adapter/           # 大模型接入适配器（多厂商支持）
├── 💬 chat_system/           # 对话聊天系统（固定单用户）
├── profiles/                 # 个体模拟配置
│   └── default.json           # 默认配置
├── cli.py                     # 命令行交互入口
├── web_console.py             # 网页控制台（FastAPI）
├── agent.py                   # Agent 主程序
├── test_full_system.py        # 全系统集成测试
├── install.ps1                # Windows 一键安装脚本
├── install.sh                 # macOS/Linux 一键安装脚本
├── Dockerfile                 # Docker 镜像构建
├── requirements.txt           # Python 依赖
├── README.md
└── LICENSE
```

---

## 🆚 和 OpenClaw 的对比

| 对比项 | 聚活 | OpenClaw |
|--------|------|----------|
| **定位** | 个人数字分身 + AI Agent 自我进化引擎 | 多平台消息网关 |
| **依赖** | Python 3.8+，仅需几个 pip 包 | Node.js 20+ + pnpm |
| **安装难度** | ✅ 非常简单，一键完成 | ⚠️ 需要配置 Bot 账号，网络容易卡 |
| **独立运行** | ✅ 自带网页控制台，可独立使用 | 需要对接 CoPaw/Clawdbot |
| **核心功能** | 模拟个人思维，持续自我进化 | QQ/Discord 等平台消息转发 |
| **需要 Bot 账号** | 不需要 | 需要 |

---

## 📖 设计理念

1. **持续进化** — Agent 不是写完就固定了，要从经验中学习，自动改进
2. **结构化判断** — 遇到复杂问题，用十维框架系统性思考，不跟着感觉走
3. **分离维度** — `generation` 记录派生深度 / `fix_version` 记录修正次数，两个维度完全分离
4. **保持一致** — 级联重新验证保证整个技能谱系一致性
5. **合理简化** — 跳过 OpenSpace 过度工程部分，保留核心设计价值
6. **固定单用户** — 专为"一个人打造自己的数字分身"设计，所有数据本地存储，完全私密

---

## 📄 License

MIT License — 欢迎学习、使用、改进。

---

> *"起点是模仿具体的人，终点是在意识和思想上超越人类整体。"*
