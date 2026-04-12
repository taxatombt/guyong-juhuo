# computer-operator
Careful local computer operation: verified steps, safe changes, reversible, documented

## Description

Operator for local computer tasks: file edits, command execution, debugging, configuration. This is the **codex-workflow** specialized for local computer operation.

## When to use

- Any task that involves changing files/running commands on the local machine
- Debugging existing code/configurations
- Installing software and dependencies
- Making backups before changes
- System configuration
- Multi-step file operations

## Workflow

### 1. Survey the scene
- `pwd` / `ls` → where are we?
- `cat` relevant files → what's here already?
- Check git status → clean or dirty?
- List what we know, list what we don't know

### 2. Plan the steps
- Break into smallest possible steps
- Each step produces verifiable output
- Identify rollback command for each step
- Ask confirmation before destructive steps

### 3. Execute & Verify
- Run one step
- **Immediately verify** the result (check file content / check command output)
- If wrong → rollback → adjust plan → retry
- If right → proceed to next step

### 4. Document
- Update documentation if changed
- Note any deviations from the plan
- Log what you learned for next time

## Safety Rules

1. **Confirm before destruction**
   - `rm` / `del` / `git reset --hard` / `DROP TABLE` always ask
   - Make backup before overwriting

2. **Prefer safe commands**
   - `cat` not `vim` for reading
   - `diff` before applying changes
   - `git status` before committing

3. **Reversible first**
   - Can we test this on a copy? Yes.
   - Can we easily rollback? Yes.

4. **No blind pipes**
   - `curl | bash` is dangerous → download first, inspect, then run
   - Same for `wget | python`

## Integration with 聚活 (guyong-juhuo)

Computer operator is the practical application of codex-workflow to local machine. It uses:
- `openspace-evolution` → automatically creates/improves skills for repeated operations
- `verification-agent` → independent verification after changes
- `causal-memory` → records what worked what failed for future reference

## Why this works

The biggest problem with AI local operation is **going too fast, skipping verification**. This workflow forces you to **slow down, verify every step, keep it reversible**. That matches Hermes's philosophy: *careful beats fast*.
