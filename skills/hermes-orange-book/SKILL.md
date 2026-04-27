# Hermes Agent 橙皮书啃读笔记

> 来源：花叔《Hermes Agent 从入门到精通》橙皮书 + 三篇详细解读
> 啃读：juejin.cn/post/7627109086874517547、juejin.cn/post/7630651226246529043、juejin.cn/post/7626220258146238490
> 时间：2026-04-27

---

## 一、核心定位：Hermes vs OpenClaw

| 维度 | Hermes Agent | OpenClaw |
|------|-------------|----------|
| 设计原点 | 成长型搭档（Agent为中心） | 数字中枢（Gateway为中心） |
| 记忆 | 原生三层记忆，闭环自进化 | Gateway统一管控，记忆为插件 |
| Skills | 原生自动沉淀，闭环进化 | 手动创建/市场下载 |
| 进化 | 原生自我学习闭环 | 无，依赖外部Skill市场 |

Hermes隐喻：「数字同事」—— 会跟你一起成长，主动固化成功经验。

---

## 二、Skills闭环系统

### 2.1 完整闭环
创建：经验提取 -> 知识存储 -> 智能检索 -> 渐进揭示
改进：质量评估 -> 迭代优化 -> 版本回滚

### 2.2 创建四阶段

#### Stage 1：经验提取
触发：>=5步复杂任务完成。5维评分：
综合分 = 频率*0.2 + 复杂度*0.2 + 成功率*0.25 + 可复制性*0.2 + 独立性*0.15
>=8分 -> 自动创建 | 5-7分 -> 待验证 | <5分 -> 仅日志

#### Stage 2：知识存储（agentskills.io标准）
```yaml
name: skill-name
trigger:
  keywords: [react, component, review]
  context_pattern: 代码规范...
steps:
  - step: 1. 检查项目结构
    tool: Read; path: {project}/src
validation:
  - 类型: 输出包含代码Review
examples:
  - input: 帮我Review一下Button组件
    output: 按照代码规范...
```

#### Stage 3：智能检索
双层：关键词倒排（粗排）+ embedding语义（精排）
score = keyword*0.3 + semantic*0.4 + usage*0.15 + recency*0.15

#### Stage 4：渐进揭示（Progressive Disclosure）
Layer 0: 无Skill，AI独立完成
Layer 1: 技能发现 -> 我注意到这类问题可能需要X技能
Layer 2: 用户决定 -> 是否启用X技能？
Layer 3: 自动执行 -> 用户已授权，直接调用

### 2.3 自改进三阶段

#### Stage 5：质量评估（5维）
quality = success_rate*0.35 + user_rating*0.25 + error_rate*0.20 + time*0.10 + adoption*0.10

#### Stage 6：迭代优化
- 质量上升 -> 扩大触发范围
- 质量下降 -> 缩小触发范围
- 质量 < 阈值 -> 标记待审查

#### Stage 7：版本回滚
触发：新版本质量 < 旧版本*0.8（连续3次）
保留versions/历史版本，自动回滚并通知

### 2.4 安全扫描器
BLOCK: rm -rf /, os.environ[KEY], eval/exec, curl|wget|sh, nc -e, drop database
WARN: os.system, subprocess, requests.post, open(...w)

---

## 三、三层记忆系统

| 层级 | 容量 | 内容 | 更新 |
|------|------|------|------|
| L1 MEMORY.md | 2200 chars | 硬性事实（项目结构）| 手动 |
| L2 USER.md | 1375 chars | 用户画像（偏好、工作流）| 自动 |
| L3 Competitive | 动态竞争 | 临时经验，优胜劣汰 | 自动 |

竞争性存储：新记忆 importance_score = frequency*0.25 + recency*0.25 + uniqueness*0.25 + utility*0.25

双轨用户画像：
- Hard Facts: 用户直接告知
- Soft Profile: Honcho从对话推断（debug导向/夜猫子/重视原理）

---

## 四、juhuo落地分析

| Hermes特性 | juhuo现状 | 差距 |
|-----------|-----------|------|
| 三层记忆竞争淘汰 | L1 biography/L2 experiences/L3 perception | L2缺竞争淘汰 |
| Skill自动沉淀 | evolver权重进化（不创建Skill） | 未实现 |
| 渐进揭示4层 | 直接输出判断结果 | 未实现 |
| 二层Skill缓存 | experiences FTS5 | 对等 |
| 安全扫描 | 无 | 待实现 |
| Honcho推断 | 无 | 待实现 |
| 质量评分user_rating | evolver缺此维度 | 待加 |
| 版本回滚 | evolver rollback | 对等 |

落地优先级：
P0: quality_score加user_rating维度
P1: ProgressiveDisclosure渐进揭示
P2: Skill二层缓存、Honcho软画像
P3: Skill安全扫描、L2竞争淘汰

渐进揭示设计：
Layer 1: 这类决策通常涉及X维度，是否需要展开？
Layer 2: verdict + 置信度 + 是否输出10维？
Layer 3: 完整10维判断输出

---

## 五、核心教训

1. 渐进揭示 > 直接给答案，保持用户掌控感
2. Skill沉淀触发点：>=5步复杂任务
3. 竞争性存储防MEMORY膨胀
4. 质量评分必须有user_rating
5. 安全扫描是Skill创建的前提
6. Hermes=Agent进化驱动 vs OpenClaw=Gateway中心化

---

## 六、啃读来源

juejin.cn/post/7627109086874517547 -- 三层记忆+Skill沉淀+双轨画像+三陷阱
juejin.cn/post/7630651226246529043 -- Skills闭环7阶段+二层缓存+渐进揭示
juejin.cn/post/7626220258146238490 -- Hermes vs OpenClaw架构对比+设计哲学
PDF（待下）: alchaincyf/hermes-agent-orange-book (2.6k★)，GitHub 443阻断

_Last updated: 2026-04-27_
