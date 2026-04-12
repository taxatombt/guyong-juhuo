---
name: self-evolution
description: 聚活系统自进化任务，使用 gstack 虚拟工程团队对聚活自身改进需求进行多专家评审。
tags: [evolution, gstack, self-improvement, juhuo]
author: juhuo
version: 1.0.0
---

# 聚活自进化任务

## Objective
对聚活(JuHuo)个人数字分身系统的改进需求，使用 gstack 虚拟工程方法论进行多专家评审，保证改进质量，减少设计盲区。

## When to Trigger
- 用户要求改进聚活自身功能
- 需要添加新模块到聚活系统
- 需要重构聚活现有模块
- 修复聚活系统bug

## Inputs
- 改进需求描述（文字）
- 现有代码路径（可选）
- 期望输出（功能描述）

## Core Workflow
1. 创建 gstack 虚拟团队实例，配置必要专家角色
2. 启动自进化任务，传入改进需求
3. 按顺序运行每个专家评审：
   - CEO评审（策略范围）
   - 架构评审（设计边界）
   - 安全评审（OWASP检查）
   - QA评审（测试覆盖）
   - DX评审（开发体验）
   - 文档更新
4. 收集所有评审发现
5. 输出汇总报告，包含所有问题和建议
6. 等待用户批准后执行修改

## Commands
```python
from juhuo.gstack_virtual_team import create_juhuo_virtual_team
vt = create_juhuo_virtual_team(llm_config_path="config/llm.json")
vt.start_evolution_task("Add new feature X...")
# 逐步执行每个评审
```

## Best Practices & Guidelines
- 保持当前：用户已经要求简化，不做过度工程
- 身份锁原则：CORE_IDENTITY 不允许自动进化，需要用户明确批准
- OpenSpace DAG 版本管理：每次进化增加正确版本号
- 保存快照：每次重大进化自动保存系统快照

## References
- `references/gstack-principles.md` - gstack 核心原则
- `../../gstack_virtual_team/README.md` - 虚拟团队集成

## Examples
```python
# 开始自进化任务
from juhuo.gstack_virtual_team import create_juhuo_virtual_team
vt = create_juhuo_virtual_team()
result = vt.start_evolution_task("Improve the curiosity engine exploration balance")
print(result)
```
