# Juhuo 更新日志

## v1.3 (2026-04-16)

### Codex Rust启发实现

| 文件 | 功能 | 来源 |
|------|------|------|
| `judgment/protocol.py` | ExitCode协议 + JudgmentResult标准化 | Codex ExitCode |
| `judgment/matcher.py` | 规则Matcher，检测危险命令 | Codex Matcher模式 |
| `judgment/pre_tool_hook.py` | PreToolUse + PostToolUse钩子 | Codex PreToolUse Hook |
| `judgment/life_cycle_hooks.py` | 11个钩子 (Hermes 9 + Codex 2) | Codex HookEvent |

### 核心功能

#### 1. ExitCode协议
```python
class ExitCode(Enum):
    SUCCESS = 0      # 可信，执行
    NEED_VERIFY = 1  # 需要验证
    REJECTED = 2     # 拒绝
    UNCERTAIN = 3    # 不确定
    TIMEOUT = 4      # 超时
    ERROR = 5        # 错误
```

#### 2. Matcher危险命令检测
```python
check_safe("rm -rf /")  # -> blocked=True, reason="递归强制删除（危险）"
check_safe("sudo rm -rf /")  # -> blocked=True
check_safe("ls -la")  # -> blocked=False, safe
```

#### 3. PreToolUse安全钩子
```python
pre_action_check("execute", {}, "rm -rf /")
# -> PreToolUseOutcome(action=BLOCK, should_block=True, block_reason="危险命令")

pre_action_check("execute", {}, "ls")
# -> PreToolUseOutcome(action=ALLOW, should_block=False)
```

#### 4. LifeCycleHooks 11个钩子
```python
# Hermes 9个
1. build_system_prompt()     ✅ 收集系统提示块
2. prefetch_all(query)        ✅ 每轮前背景召回
3. sync_all(user, asst)       ✅ 每轮后异步写入
4. on_turn_start()            ✅ 新Turn开始
5. on_turn_end()              ✅ Turn结束
6. on_pre_compress()          ✅ 压缩前
7. on_memory_write()          ✅ 写入时
8. on_delegation()            ✅ 子Agent完成
9. on_session_end()           ✅ 会话结束

# Codex 2个
10. on_pre_action()           ✅ 动作执行前 (Codex)
11. on_post_action()          ✅ 动作执行后 (Codex)
```

#### 5. PostToolHook工具执行记录
```python
# 记录到SQLite
tool_executions表:
- tool_name, success, output, error, duration_ms, executed_at
```

### 规则表

| 规则名 | 模式 | 级别 |
|--------|------|------|
| dangerous_delete | `rm\s+-rf` | BLOCK |
| privilege_escalation | `sudo\s+` | WARNING |
| system_modify | `chmod\s+777\|chown\s+` | WARNING |
| network_fetch | `curl\|wget\s+` | CAUTION |
| api_key_expose | `(api_key\|secret\|password)\s*=\s*` | BLOCK |
| kill_process | `kill\s+-(9\|TERM)` | WARNING |
| fork_bomb | `:\(\)\{.*:\|:&\}*` | BLOCK |
| overwrite_etc | `(>|>>)\s*/etc/` | DANGER |
| write_sudoers | `(>|>>)\s*/etc/sudoers` | BLOCK |
| git_force_push | `git\s+push\s+.*\s+-f` | WARNING |
| git_dangerous | `git\s+.*--force` | CAUTION |

---

## 历史版本

### v1.2 (2026-04-16)
- Hermes 9个钩子全部实现
- 五阶段压缩升级 (Prune→Protect→Summarize→Iterative)
- 上下文围栏 context_fence.py
- Stop Hook事件捕获
- 四道压缩叠加 (Snip→Micro→Collapse→Auto)
- SQLite数据层
- 十维推理规则引擎

### v1.1 (2026-04-15)
- P0: 因果推断引擎 causal_inference.py
- P0: self_model贝叶斯追踪
- P1: fitness反馈循环
- P1: 验证层 verifier.py
- P2: SQLite数据层

### v1.0 (2026-04-14)
- Juhuo基础架构
- judgment判断系统
- causal_memory因果记忆
- curiosity好奇心引擎

---

_最后更新：2026-04-16_