# gstack 核心原则

来自 garrytan/gstack 虚拟工程团队方法论：

## 核心原则

1. **每个人只做专家领域** - 每个专家只负责自己专业领域，不越界评论其他领域

2. **Zero silent failures** - 每个失败模式都必须可见，不沉默

3. **Boil the Lake** - AI 边际成本接近零，做完整的事

4. **Search Before Building** - 先搜索，再从零开始

5. **User Sovereignty** - AI 推荐，用户决策，用户永远在中心

6. **Inversion** - 先问 "what would make us fail?" ，避免那些路径

7. **Focus as subtraction** - 主要价值增值是告诉你 **不要做什么**

## 工作流顺序

标准顺序：
```
CEO → Product → Architect → Design → Frontend → Backend → Security → QA → DevEx → Docs
```

最小顺序（自进化常用）：
```
CEO → Architect → Security → QA → Docs
```

## 评审输出格式

每个评审必须：
- 按严重性分组 (critical/major/minor/info)
- 每个发现包含：分类、描述、建议、位置（如果有
- 结尾总结，明确是否 approve (passed = true/false)

## 临界问题规则

- 任何 critical 问题必须解决才能继续
- 不跳过 critical 问题
- 用户必须确认解决后才能进入下一步
