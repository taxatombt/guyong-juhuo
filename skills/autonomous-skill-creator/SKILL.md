# autonomous-skill-creator
Closed-loop autonomous skill creation and improvement — from Hermes-Agent

## Description

**Closed Learning Loop:** Agent autonomously detects opportunities for new skills, creates them, and improves them automatically during usage. *Not waiting for user correction — active learning*.

This is the core insight from Hermes-Agent (NousResearch):
> Agents can curate their own memory and create/improve their own skills automatically.

## Closed Loop

```
Complex task execution
    ↓
Detect skill opportunity (score ≥ 0.5)
    ↓
Agent autonomously suggests creating a new skill
    ↓
User approves → Skill is created with .skill_id (OpenSpace DAG)
    ↓
Skill is used
    ↓
Track effectiveness automatically during usage
    ↓
Effectiveness < threshold → automatically derive improved version (OpenSpace DERIVED)
    ↓
Repeat → continuous improvement
```

## Integration with OpenSpace / 聚活

This fits perfectly with 聚活's OpenSpace Version DAG architecture:

| Hermes Stage | OpenSpace Equivalent |
|--------------|----------------------|
| New skill captured | `CAPTURED` (gen=0) |
| Derive improved version | `DERIVED` (gen+1) |
| Fix bug in place | `FIX` (fix_version+1) |
| Automatic cascade revalidation | OpenSpace native cascade |

## Scoring Skill Opportunity

Score 0.0-1.0 for whether this task should be a skill:

- `+0.3` if it's repeatable
- `+0.3` if it follows a consistent pattern
- `+0.2` if it solves a general problem not solved by existing skills
- `+0.2` if you've done this task before (pattern confirmed)

**If ≥ 0.5 → suggest creating skill.**

## Effectiveness Tracking

After skill is used:
- Track success/failure
- Track user corrections
- If failure rate > threshold → trigger automatic improvement (DERIVED)

## When to use

- After completing a complex task that seems generally useful
- When you notice you're doing the same pattern repeatedly
- When you create something that could be reused

## User Interaction

- Agent suggests: "This seems like a reusable pattern. Should I create a skill for it?"
- User says yes → create skill in `skills/` with proper `.skill_id` and SKILL.md
- User says no → don't create, remember for next time

## 聚活 Benefits

Adding this to 聚活 gives us **true autonomous self-improvement**:
- Agent doesn't just wait for you to tell it what to learn
- It actively looks for patterns and turns them into skills
- It automatically improves skills that don't work well
- Over time, the agent gets better and better at doing the tasks you do repeatedly

This is exactly what "聚活" means: *your patterns and knowledge聚沙成塔, alive and growing*.
