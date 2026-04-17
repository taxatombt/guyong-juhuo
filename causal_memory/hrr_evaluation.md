# HRR 向量检索评估报告

**评估日期：** 2026-04-17  
**TODO 编号：** #5  
**结论：** 当前规模下 **不需要** 向量搜索升级。条件触发器已设定。

---

## 当前实现

| 项目 | 值 |
|------|------|
| 检索方式 | `difflib.SequenceMatcher` 字符串相似度 |
| 阈值 | `SIMILARITY_THRESHOLD = 0.65` |
| 数据源 | `causal_memory/events.db` (SQLite) |
| 函数 | `find_similar_events(task, max_results=3)` |

---

## 评估维度

| 维度 | 当前状态 | 需求 | 结论 |
|------|---------|------|------|
| 语义相似度 | 字符级 diff | 需要语义理解 | ❌ 弱 |
| 性能 | O(n×m) per query | <100ms | ⚠️ 中（50条内OK）|
| 依赖 | 零外部依赖 | 可离线运行 | ✅ 强 |
| 可调试性 | 完全透明 | 日志友好 | ✅ 强 |
| 扩展性 | 1000+条变慢 | 1000+条 | ❌ 弱 |

---

## 规模推算

| 阶段 | Verdict 数量 | difflib 延迟 | 是否需要向量 |
|------|-------------|-------------|-------------|
| 当前 | ~42 条 | ~5ms | ❌ 不需要 |
| 进化就绪 | 50 条 | ~6ms | ❌ 不需要 |
| 中期 | 200 条 | ~25ms | ❌ 可接受 |
| 长期 | 500+ 条 | ~100ms+ | ⚠️ 建议评估 |
| 成熟 | 1000+ 条 | ~300ms+ | ✅ 需要 |

---

## 升级触发条件

当以下任一条件满足时，应启动向量搜索升级：

```python
TRIGGER_VECTOR_SEARCH = {
    "min_events": 500,          # 事件总量
    "min_judgments": 200,         # verdict 案例数
    "avg_query_latency_ms": 100,  # 平均查询延迟
    "recall_rate": 0.7,           # 相似事件召回率 < 70%
}
```

---

## 升级方案（当触发时）

### 方案 A：轻量嵌入（推荐用于 500-2000 条）
- 使用 `sentence-transformers` 轻量模型（`all-MiniLM-L6-v2`）
- 本地 SQLite 扩展：存储 `event_embedding BLOB`
- 不需要独立向量数据库
- 迁移成本低

```python
# 嵌入字段（新增）
ALTER TABLE events ADD COLUMN embedding BLOB;

# 插入时自动生成
def record_event_with_embedding(...) -> int:
    embedding = embed(event_text)  # ~384维 float32
    conn.execute("INSERT INTO events ... embedding=?", (embedding,))
```

### 方案 B：专用向量库（用于 2000+ 条）
- Qdrant / ChromaDB / pgvector
- 需要额外服务部署
- 适合有运维资源的团队

---

## 决策

**暂不升级，条件触发：**

1. 在 `judgment/config.py` 中添加 `TRIGGER_VECTOR_SEARCH` 配置
2. 在 `verdict_collector.run_full_collection()` 末尾输出向量升级建议
3. 每年 Review 时重新评估

---

_评估完成 — 2026-04-17_
