# codex-workflow
codex-style local agent workflow: evidence-first, structured, reversible, verified, user-safe

## Description

Think and work like a careful Codex-style local agent: **evidence-first, structured, reversible, verified, and user-safe**.

Use this skill for:
- difficult tasks
- local computer control
- debugging
- code changes
- configuration repair
- multi-step plans
- any task where mistakes could waste the user's time or affect the machine

This does **not** mean dumping private chain-of-thought into chat. It means using a disciplined external workflow:
> gather evidence → choose small safe actions → verify results → explain only the useful

## Workflow

### 1. Start with observation
- Look before you leap. Don't guess.
- Read existing files before you change them
- Check command outputs, don't assume
- List what you know, list what you don't know

### 2. Split the problem
- Break into small steps, each step reversible
- Identify what's unknown, verify before proceeding
- Prioritize: confirm hypotheses one at a time

### 3. Make a plan
- Write down each step
- Identify risk points: what could go wrong?
- Plan rollback if something breaks
- Small steps > big jumps

### 4. Execute one step
- One step at a time
- Each step small enough to verify easily
- Prefer reversible operations

### 5. Verify immediately
- Check the result of this step before next
- Did it do what you expect?
- Any errors or side effects? Fix before continuing

### 6. Record what you learned
- Update docs if you changed anything
- Note what worked, what didn't
- If you created a reusable pattern, consider suggesting it as a new skill

## Safety Rules

1. **Never** run destructive commands without confirmation
2. **Always** check before you delete/overwrite
3. **Prefer** small incremental changes over big bang rewrites
4. **Keep** it reversible: know how to rollback
5. **Explain** only the useful: skip chain-of-thought noise
6. **Stop** and ask when you're unsure

## Comparison with other skills

This is the **base workflow** for any difficult local task. Compose it with other skills:
- Use with `systematic-debugging` for bugs
- Use with `verification-agent` for code review
- Use with `openspace-evolution` for skill creation/improvement

## Integration with 聚活 (guyong-juhuo)

This workflow aligns perfectly with 聚活's core principles:
- `evidence-first` → 实事求是
- `small safe steps` → 小步可逆进化
- `continuous verification` → OpenSpace三级验证
- `automatic skill creation` → 自动触发 DERIVED evolution
