# guyong-juhuo · 聚活

<p align="center">
  <img src="logo.svg" width="320" alt="juhuo logo">
</p>

**一个会进化的个人数字分身。**

模拟特定个体的思维方式，在判断力上超越人类整体。

> 🌍 **English version:** [README_en.md](README_en.md)

---

## 项目介绍

### 是什么

juhuo是一个个人AI判断系统，具有以下核心能力：

- **十维判断系统** - 从多维度分析两难问题
- **因果记忆** - 追踪判断与结果的因果关系
- **Fitness反馈循环** - 自我进化的评分机制
- **危险命令检测** - PreToolUse/PostToolUse安全钩子

### 能做什么

```
判断两难问题：
python cli.py "我应该接受这个offer还是继续找?"

危险命令检测：
"rm -rf /" → 拦截

因果推断：
用户抱怨速度慢 → 推断原因：数据库负载高
```

### 架构

```
judgment（判断）
    ↓
causal_memory（因果记忆）
    ↓
self_model（自我模型更新）
    ↓
下次判断改善（闭环）
```

### 目录结构

```
juhuo/
├── judgment/          # 十维判断系统
├── causal_memory/     # 因果记忆
├── self_model/        # 自我模型（贝叶斯盲区追踪）
├── curiosity/         # 好奇心引擎（锁定兴趣域+双随机游走）
├── emotion_system/    # 情感系统（情绪信号检测）
├── mcp/               # MCP 客户端（MCP服务器集成）
├── skills/            # Skill 系统（含 Skill Self-Evolver）
├── tools/             # 52个工具接口
├── evolver/           # Self-Evolver 验证闭环
├── judgment/          # 判断核心 + 多模块
│   ├── compactor.py   # 历史压缩
│   ├── multi_agent.py # 多Agent编排
│   ├── exec_policy.py # 权限控制
│   ├── session.py     # 会话持久化
│   ├── auto_evolver.py # 全模块自我进化
│   └── logging_config.py # 日志系统
├── web/               # 网页控制台
├── tui.py             # 终端界面
├── test/              # 测试套件
├── cli.py             # 命令行入口
└── launcher.bat       # 启动器
```

### Emotion → Judgment 集成

```
emotion_system (情绪分析)
        ↓
emotion_output → 注入 judgment_context["emotion_state"]
        ↓
judgment_engine 在做 verdict 时能看到情绪状态
        ↓
情绪信号 → 影响维度权重（如焦虑→降低自信度）
```

### 自我进化闭环

| 模块 | 进化目标 | 触发条件 |
|------|---------|---------|
| Judgment | 调整判断权重 | 准确率下降 |
| Skill | 优化触发条件 | 成功率 < 30% |
| Compaction | 调整压缩阈值 | 保留率 < 70% |
| Multi-Agent | 优化Agent协作 | 成功率 < 80% |
| Exec Policy | 调整危险模式 | 误报率 > 30% |

---

## 📥 下载安装（两种方式）

### 方式一：从项目压缩包下载（推荐）

**步骤：**

1. 点击本页面顶部的 **Code** 按钮（绿色按钮）

2. 点击 **Download ZIP**

3. 解压下载的ZIP文件到任意位置

4. 在解压后的文件夹中找到 **`juhuo.exe`**（约100MB）

5. 双击 `juhuo.exe` 运行

**解压后文件夹结构：**
```
guyong-juhuo-main/
├── juhuo.exe          ← 双击这个文件！
├── judgment/          # 判断系统（源码，可不看）
├── causal_memory/     # 因果记忆（源码，可不看）
├── launcher.bat       # 启动脚本（源码，可不看）
├── README.md          # 本文件
└── ...                # 其他源码文件
```

---

### 方式二：单独下载exe

**步骤：**

1. 点击页面右侧的 **Releases** 或访问：
   ```
   https://github.com/taxatombt/guyong-juhuo/releases
   ```

2. 下载 `juhuo.exe`

3. 双击运行

---

## 🚀 使用方法

1. **双击 `juhuo.exe`**
2. 等待程序启动（自动打开浏览器）
3. 在浏览器中访问 **http://localhost:9876**

**完成！不需要Python，不需要安装，不需要任何依赖。**

---

## 🔧 从源码运行（开发者）

```bash
# 安装依赖
pip install -r requirements.txt

# 运行网页控制台
python web_console.py

# 或用启动器
launcher.bat

# 命令行判断
python cli.py "你的问题"
```

---

## ❓ 常见问题

### Q: 双击后什么都没发生？
**A**: 检查是否双击的是 `juhuo.exe`，不是其他文件。

### Q: 提示"Windows已保护你的电脑"？
**A**: 点击"更多信息"→"仍要运行"。这是正常的Windows安全提示。

### Q: 没有自动打开浏览器？
**A**: 手动打开浏览器，输入地址 `http://localhost:9876`

### Q: 怎么关闭程序？
**A**: 在程序运行的黑色命令行窗口按 `Ctrl+C`

### Q: 怎么卸载？
**A**: 直接删除 `juhuo.exe` 即可，无需其他操作。

---

## 🖥️ Web控制台

程序运行后，自动打开浏览器访问 `http://localhost:9876`

**功能：**
- 查看当前判断状态
- 手动触发判断
- 查看因果记忆
- 查看自我模型（盲区/优势）
- 查看进化历史

---

## 🧠 好奇心引擎 (curiosity/)

**锁定兴趣域 + 双随机游走**

普通AI好奇心会瞎探索什么都感兴趣，聚活不是：

### 核心原理

1. **锁定兴趣域**：只探索符合锁定兴趣方向的话题，不跑题
   - 兴趣列表永久锁定（核心身份锁）
   - 不符合锁定域的话题直接过滤

2. **双随机游走**：
   - 80%概率走目标导向路径（服务当前任务）
   - 20%概率自由随机游走（保留意外发现）

3. **三触发机制**：
   - 知识缺口触发 → 判断置信度低
   - 未知异常触发 → 因果不匹配
   - 价值相关性触发 → 和长期目标沾边

### 优先级

```
1. 对齐长期目标 → 最高优先级
2. 服务当前任务 → 第二优先级
3. 锁定兴趣域自由游走 → 低优先级但每日必占一位
4. 完全无关 → 过滤掉
```

---

## 💭 情感系统 (emotion_system/)

**情绪信号检测**

核心问题：**当前判断带来了什么情绪？这个情绪是不是一个需要重视的信号？**

### 核心逻辑

1. 从判断文本 + 决策过程中提取情绪标签
2. 判断情绪是不是「需要重视的信号」：
   - 焦虑 → 信息不足/风险不确定 → 需要提醒
   - 兴奋 → 高价值机会 → 需要关注
   - 平淡 → 没信号，不用管
3. 信号自动注入判断上下文

### 设计原则

- 严格依赖顺序：情绪来自判断过程
- 接口简单：只暴露两个核心方法
- 从小做起：不模拟完整人类情感，只做信号检测
- 持续学习：每次反馈后更新情绪-信号模式

---

## 🔄 Self-Evolver 自动闭环

**核心原理：**

```
判断完成 → Fitness评分 → 偏差计算
              ↓
        self_model更新（贝叶斯盲区追踪）
              ↓
        偏差超过阈值？→ 触发规则重训
              ↓
        新旧规则对比 → 优胜劣汰
              ↓
        保存进化记录
```

**关键参数：**
- 偏差阈值：0.7（连续3次超过触发重训）
- 准确率阈值：0.4（某维度低于此值触发）
- 冷却时间：24小时（避免频繁重训）

### 进化机制

```
判断完成 → verdict_outcomes 表记录
                ↓
    check_trigger() 检查阈值
                ↓
    触发 → get_cases() 获取历史案例
                ↓
    compute_new_weights() 计算新权重
                ↓
    compare() 新旧规则对比
                ↓
    新规则更好 → apply_evolved_weights()
                    ↓
            self_model.json + evolved_weights.json
                    ↓
            下次判断使用新权重
```

### CLI 命令

```bash
# 十维判断
python cli.py "要不要辞职创业"

# 查看判断统计
python cli.py --stats

# 查看历史
python cli.py --history

# 运行 Self-Evolver 闭环
python cli.py hub evolver

# 查看好奇心清单
python cli.py curiosity list
python cli.py curiosity add "你的探索问题"
python cli.py curiosity close 1 answer "探索答案"

# 查看维度准确率
python cli.py --lessons
```

---

## 📁 文件说明

| 文件/文件夹 | 是否需要 | 说明 |
|------------|---------|------|
| **juhuo.exe** | ✅ 必须 | 程序入口，双击运行 |
| judgment/ | ❌ 可忽略 | 判断系统源代码 |
| causal_memory/ | ❌ 可忽略 | 因果记忆源代码 |
| launcher.bat | ❌ 可忽略 | 启动脚本（源码版用） |
| README.md | ❌ 可忽略 | 本文件 |

---

## 技术规格

| 项目 | 说明 |
|------|------|
| 文件大小 | ~100MB |
| 运行环境 | 无需Python（已内置） |
| 是否需要安装 | 否，直接运行 |
| 占用端口 | 9876 |

---

## 铁律

> **模拟特定具体个体，最终在判断力上超越人类整体。**

---

## 技术支持

- GitHub: https://github.com/taxatombt/guyong-juhuo
- Releases: https://github.com/taxatombt/guyong-juhuo/releases

---

_最后更新：2026-04-17 v1.5_