# guyong-juhuo · 聚活

**一个会进化的个人数字分身。**

模拟特定个体的思维方式，在判断力上超越人类整体。

> 🌍 **English version:** [README_en.md](README_en.md)

---

## 目录结构

```
guyong-juhuo/
│
├── judgment/          # 十维判断系统
│   ├── router.py     # 入口：根据输入路由到对应维度
│   ├── dimensions.py  # 十维定义（认知×博弈×经济×辩证×情绪×直觉×道德×社会×时间×元认知）
│   ├── dynamic_weights.py    # 动态权重：随情绪/场景变化
│   ├── priority_output.py    # P0-P4 分级格式化输出
│   ├── self_review.py        # 教训记录 + 漏用检测 + PATTERN×N 纠错
│   ├── error_classifier.py   # 错误分类（quota/auth/transient/busy/generic）
│   ├── fitness_baseline.py  # 个人一致性健康度基线
│   ├── confidence.py         # 置信度评分（直觉维度）
│   ├── metacognitive.py      # 元认知：知道自己的思维盲区
│   └── insight_tracker.py    # 洞察记录（好奇系统副产品）
│
├── curiosity/        # 好奇心引擎
│   ├── curiosity_engine.py   # 双随机游走（80%目标导向/20%自由探索）
│   └── ralph_loop.py         # Ralph 自引用循环：completion promise 驱动终止
│
├── feedback_system/  # 反馈处理
│   ├── feedback_system.py    # 双层反馈闭环：判断层 + 进化层
│   └── observe_hook.py       # 被动工具调用捕获（5层自防）
│
├── output_system/    # 输出格式化
│   ├── output_system.py      # 输出时机决策算法（何时输出何时沉默）
│   ├── formatter.py          # 分级格式化（brief=只P0/P1 / full=全部 / structured=JSON）
│   └── conversation_formatter.py  # 对话格式化
│
├── action_system/   # 行动规划
│   ├── action_system.py      # 四象限时间压强排序 + 执行信号生成
│   └── security_hook.py       # 10种危险模式检测（PreToolUse 级别）
│
├── openspace/        # Skill 进化系统
│   ├── autonomous_skill_detector.py  # 自动发现可进化点
│   └── collision_detector.py         # Skill 触发条件碰撞检测
│
├── emotion_system/  # 情感系统
│   └── emotion_system.py    # PAD 三维模型（愉悦度×激活度×支配度）
│
├── causal_memory/    # 因果记忆
│   ├── causal_memory.py     # 快慢双流：快=即时记录 / 慢=批量因果推断
│   ├── causal_chain.py       # 跨事件因果链追踪
│   └── types.py             # 因果事件类型定义
│
├── self_model/      # 自我模型
│   └── self_model.py        # 贝叶斯盲区追踪 + 置信度对数增长
│
├── goal_system/     # 目标系统
│   └── goal_system.py       # 洋葱时间锚定：五年→年度→月度→本周→今日
│
├── perception/      # 感知输入层
│   ├── attention_filter.py  # 主动注意力过滤 + 优先级打分
│   ├── web_adapter.py       # 网页内容提取
│   └── pdf_adapter.py       # PDF 结构化提取
│
├── chat_system/    # 对话系统
│   └── chat_system.py       # 持久化对话 + 十维判断自动触发
│
├── llm_adapter/    # 大模型适配器
│   ├── base.py     # 统一接口抽象
│   ├── minimax.py  # MiniMax 接入
│   ├── openai.py   # OpenAI 兼容接口
│   └── ollama.py   # Ollama 本地接入
│
├── web/            # 网页控制台
│   ├── app.py      # Web 服务器（TUI→HTML渲染）
│   ├── ui.html     # 前端界面
│   └── ui_sse.html # SSE 实时推送版本
│
├── docs/           # 架构文档
│
├── _legacy/        # 历史啃读代码（不保证可用）
│   ├── openspace_evolution.py   # OpenSpace 啃读
│   ├── gstack.zip               # gstack 压缩包
│   ├── gstack-main/             # gstack 源码
│   └── test_*.py / verify_*.py  # 各系统验证脚本
│
├── data/           # 数据持久化
│   └── judgment_data/
│       ├── fitness_baseline.json     # 健康度快照
│       ├── lessons.json              # 教训记录
│       ├── pattern_alerts.jsonl      # PATTERN×N 警报
│       └── fitness_snapshots/        # 版本快照
│
├── cli.py           # 命令行入口
├── judgment_cli.py   # 判断系统命令行
├── judgment_web.py   # 判断系统网页版
├── tui_console.py    # 终端图形界面
├── profile.py        # 用户身份配置
├── config.py         # 全局配置
├── launcher.bat       # Windows 启动器（init/console/tui 三模式）
├── install.ps1       # Windows 一键安装脚本
├── install.sh       # Linux/macOS 安装脚本
├── setup.iss        # Inno Setup 打包脚本（生成 exe 安装程序）
├── build_installer.py # 无 Inno Setup 的备选打包工具
└── precheck.bat     # 安装前环境检测
```

---

## 核心能力（命令行示例）

### 判断一个两难问题

```bash
python cli.py "我应该接受这个offer还是继续找?"
```

输出：十维独立评分 + 建议 + 置信度

### 判断系统（独立使用）

```bash
# 十维独立评分
python -c "
from judgment import JudgmentSystem
js = JudgmentSystem()
result = js.judge('我应该接受这个offer还是继续找?')
for dim, score in result.dimensions.items():
    print(f'{dim}: {score}')
"

# P0-P4 分级输出
python -c "
from judgment.priority_output import PriorityOutput, Priority
po = PriorityOutput()
po.add('磁盘满', Priority.CRITICAL)   # P0：立即处理
po.add('JSON语法错误', Priority.HIGH)   # P1：性能/错误
po.add('建议加索引', Priority.LOW)      # P3：优化建议
for line in po.flush(): print(line)
"
```

### 好奇心引擎

```bash
# 获取今日好奇清单
python -c "
from curiosity.curiosity_engine import CuriosityEngine
e = CuriosityEngine()
for item in e.get_daily_list():
    print(f'[{item.priority}] {item.topic}')
"

# Ralph 自引用循环
python -c "
from curiosity.ralph_loop import RalphLoop
loop = RalphLoop(promise=lambda: False, max_iterations=20)
for i in range(5):
    state = loop.step(has_new_info=(i < 3))
    print(state.message)
"
```

### 目标系统

```bash
python -c "
from goal_system.goal_system import GoalSystem
gs = GoalSystem()
print(gs.format_hierarchy())
"
```

### 情感系统

```bash
python -c "
from emotion_system.emotion_system import EmotionEngine
ee = EmotionEngine()
ee.appraise(' получил повышение!', 'unexpected_good')
print(ee.get_state())
"
```

---

## 两种判断模式

| 模式 | 说明 | 调用方式 |
|------|------|---------|
| **模仿模式** | 传入 agent_profile，强制对齐特定个体的判断方式 | `js.judge(input, profile=user_profile)` |
| **超越模式** | 十维通用判断，在判断力上超越人类整体 | `js.judge(input)` |

---

## 铁律

> **模拟特定具体个体，最终在判断力上超越人类整体。**

---

## 安装（傻瓜式，双击即用）

### ⭐ 安装包安装（推荐）
下载 `dist/guyong-juhuo-1.0.0-setup.exe`（46.5MB）双击运行 → 下一步下一步 → 完成。

自动完成：安装到 `C:\Program Files\聚活` → 桌面创建图标 → 开始菜单创建图标 → 可选立即启动

### ⭐ 免安装版
下载 `dist/guyong-juhuo.exe`（39.9MB）双击直接运行，无需安装任何依赖。

```
guyong-juhuo.exe          启动网页控制台
guyong-juhuo.exe --help   显示帮助
guyong-juhuo.exe --tui    TUI 终端界面
guyong-juhuo.exe --check  安装前环境检测
```

---

## 启动

```bash
# Windows：双击桌面"聚活"图标
# 或命令行：
launcher.bat              # 启动网页控制台（默认）
launcher.bat --init      # 初始化/重装依赖
launcher.bat --tui       # TUI 终端界面

# Linux/macOS：
bash install.sh
./launcher.bat           # 或 python web_console.py
```

---

## 安装前检测（可选）

运行前检查环境是否就绪：
```powershell
.\precheck.bat
```

## 配置

编辑 `profile.py` 或运行初始化向导设置：
- 用户身份信息
- 五年/年度目标
- 大模型 API（可选，纯规则核心不需要）

---

## 设计原则

**好的架构不是设计出来的，是进化出来的。**

- 铁律保护核心特质不被进化
- 个人一致性 fitness = "符合你会做的选择" ≠ "通用标准认为对"
- 全系统版本快照可回溯任意成长阶段
