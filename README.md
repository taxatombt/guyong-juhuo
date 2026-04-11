# guyong-juhuo &nbsp;·&nbsp; 聚活

> 聚而活，模拟具体个体，持续自我进化，最终超越。

**聚活（guyong-juhuo）** 是一个完整的 AI Agent 系统，目标：在数字世界持续学习特定个体的思维方式、判断偏好、决策模式，最终在意识、思想、判断上**超越人类整体**。

打造你自己的**个人数字分身** — 记住你的一切，代替你永远活下去。

---

## 🎯 定位

> "聚而活，在数字世界持续学习，最终超越。"

这不是通用大模型，也不是单一工具 —— 这是**数字分身**：

- 核心：从每一次判断和执行中**学习**，持续**自我进化**
- 特色：十维判断框架（认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知）
- 引擎：完整集成 **HKUDS/OpenSpace** AI Agent 自我进化框架，三级进化自动改进

---

## ✨ 特性

| 模块 | 状态 | 功能 |
|------|------|------|
| 📥 **感知输入层** | ✅ 完成 | 信息接收 + 注意力过滤，支持 **网页提取 + PDF结构化提取**，只送高价值内容进认知 |
| 🧠 **十维判断系统** | ✅ 完成 | 任何决策，十维检视 — 认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知 |
| 🧬 **OpenSpace 自我进化** | ✅ 完成 | 三级进化引擎：`CAPTURED` 捕获经验 / `DERIVED` 衍生变种 / `FIX` 就地修正，自动质量监控 + 级联验证 |
| 📚 **因果记忆** | ✅ 完成 | 快慢双流 + 时间衰减置信度，追踪因果链："因为过去 X，所以现在 Y"，个人经验优先级+50% |
| 🚀 **好奇心引擎** | ✅ 完成 | 锁定兴趣域，双随机游走：80%目标导向，20%自由探索，平衡功利和创造力 |
| 🎯 **目标系统** | ✅ 完成 | 洋葱五层时间锚定：五年→年度→月度→本周→今日，自动层级一致性检查 |
| 🔍 **自我模型** | ✅ 完成 | 贝叶斯盲区追踪，低置信度预热机制，不瞎警报，确定是盲区才提醒 |
| ⚡ **行动规划** | ✅ 完成 | 四象限时间压强自动排序，保证重要不紧急永远不被遗忘 |
| 🔄 **反馈系统** | ✅ 完成 | 双层反馈锚定：判断层更新因果/自我，进化层错误回滚，保证进化不跑偏 |
| ❤️ **情感系统** | ✅ 完成 | PAD 情绪模型，情绪作为决策信号而非干扰，影响各维度权重 |
| 🤖 **行动信号** | ✅ 完成 | 标准化 JSON 输出，机器人可直接执行，也供给其他 Agent 结构化结果 |
| 🔌 **大模型适配器** | ✅ 完成 | 统一接口支持 MiniMax/OpenAI/Ollama，可选接入，纯规则核心可完全本地运行 |
| 💬 **对话聊天系统** | ✅ 完成 | 持久化保存所有对话，自动触发全功能模块，每日自动进化，固定单用户设计 |
| 🌐 **网页控制台** | ✅ 完成 | OpenClaw 风格，左侧功能按钮，直接在浏览器聊天使用 |
| 📤 **输出决策层** | ✅ 完成 | 输出时机 + 三种格式：brief/full/structured |

---

## 🚀 多种安装方式

### 方式一：一键安装（推荐，自动配置）

#### Windows
```powershell
# PowerShell 一键脚本
irm https://raw.githubusercontent.com/taxatombt/guyong-juhuo/main/install.ps1 | iex
```

#### macOS / Linux
```bash
# Bash 一键脚本
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

然后打开浏览器访问 `http://127.0.0.1:9876` 即可使用。

### 方式三：Docker 容器安装（容器化部署）

```bash
# 拉取镜像
docker pull taxatombt/guyong-juhuo:latest

# 运行容器
docker run -d -p 9876:9876 -v $(pwd)/data:/app/data --name juhuo taxatombt/guyong-juhuo:latest
```

然后打开浏览器访问 `http://localhost:9876`。

### 方式四：开发模式（参与开发）

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
pytest test_all_imports.py -v
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
