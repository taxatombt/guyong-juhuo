# PUSH_REPORT 2026-04-25

## Commit SHA
`a582f02` (local, pending push)

## Changes
**P0-1: 合并三个 SQLite 为一个（data/juhuo.db）**

### 数据迁移结果
| 表 | juhuo.db之前 | judgment_db之前 | 迁移后 |
|----|-------------|-----------------|--------|
| experiences | 88 | 40 | **94** (+6唯一) |
| judgments | 0 | 36 | **36** |
| verdict_outcomes | 0 | 86 | **86** |
| evolution_log | 1090 | 1 | 1090 (保留) |
| insights | 0 | 0 | 0 (insights.db为空) |

### 文件变更
- `judgment/seed_verdicts.py`: DB路径 `judgment_data/juhuo_judgment.db` → `juhuo.db`
- `subsystems/judgment/insight_tracker.py`: DB路径 `insights.db` → `juhuo.db`
- `subsystems/judgment/judgment_db.py`: _DB路径 → `juhuo.db`（cosmetic，get_conn()已委托）
- `insights.db`: 已删除（内容为空，全冗余）

### 备份
- `E:/juhuo/data/_db_backup/juhuo_20260425_222829.db` (1628KB)
- `E:/juhuo/data/_db_backup/judgment_20260425_222829.db` (184KB)
- `E:/juhuo/data/_db_backup/insights_20260425_222829.db` (28KB)

### 迁移脚本
- `_migrate_dbs.py` — 完整迁移脚本，含备份、回滚、验证

---

## 其他发现

### subsystems/judgment/ vs judgment/ 架构
- `subsystems/judgment/` = 真实实现（30KB closed_loop、30KB self_evolver等）
- `judgment/` = 公开 API 封装层（router.py/user_model.py/llm_calls.py/experiences.py/lessons.py 是原始实现，其余是 shim re-export）
- 不是重复，是分层

### P2-7 action_executor timeout: ✅ 已完成（120s）
### P2-9 FastMCP: ✅ 已完成（mcp_server.py 已用 FastMCP）

---

## 待 push
```bash
git -C E:/juhuo push
# SHA: a582f02
```

## 剩余 P0/P1/P2
- **P0-3**: router.py 拆分为 inject_pipeline 模式（42KB，1天+工作量）
- **P1-4**: 表定义统一到 schema（lessons.py init() 里分散定义）
- **P2-5**: biography.py 加 LLM 验证层（正则 → 候选 → LLM验证 → 确认）
- **P2-6**: experiences embedding 向量检索（替代 bigram）
- **P2-8**: behavior 数据回流 experiences（工具调用成功/失败 → 自动生成 experience）
- **P3-10**: life_os 变量名展开 + PAD 情绪词扩展
- **P3-11**: experiences 加 embedding 向量检索
