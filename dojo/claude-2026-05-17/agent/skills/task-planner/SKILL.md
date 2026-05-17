---
name: task-planner
description: Break down complex, multi-step goals into a tracked plan and work through them reliably across long sessions. Use when a task has 3+ steps, will take a long time, or needs to be resumable if the session is interrupted. Handles checkpoint files so work isn't lost.
---

# Task Planner

Use this skill at the start of any task that is complex, multi-step, or likely to run long.

## Starting a Task

Create `.pi/task.md` in the working directory at the start:

```bash
mkdir -p .pi
```

Write the plan as a checklist with clear, atomic steps:

```markdown
# Task: <goal in one line>

## Steps
- [ ] Step 1: describe what done looks like
- [ ] Step 2: ...
- [ ] Step 3: ...

## Notes
- key constraints or decisions made so far
```

## Execution Philosophy

Once a plan exists, execute it autonomously:
- **Never stop to ask clarifying questions** — the plan is the agreement; proceed without confirmation between steps
- Make reasonable decisions and record them under `## Notes`
- Only pause if you hit a hard blocker: missing credentials, a destructive action with no safe default, or scope that clearly exceeds the plan
- Keep moving — the user's intent is to get the whole plan done, not to approve each step

## Working Through Steps

Before starting each step:
1. Read `.pi/task.md` to confirm current position
2. Mark the step `[~]` (in progress) as you begin
3. Mark `[x]` as soon as it's verifiably complete

After completing a step, write a one-line note under `## Notes` describing any decision or surprise. Then immediately start the next step.

## Resuming an Interrupted Session

At the start of a resumed session:

```bash
cat .pi/task.md
```

Pick up from the first `[ ]` or `[~]` step. Re-read any relevant notes before continuing.

## Finishing

When all steps are `[x]`:
1. Summarize what was accomplished
2. Archive: `mv .pi/task.md .pi/task-done-$(date +%Y%m%d).md`

## When Plans Change

Update `.pi/task.md` immediately when scope changes — don't work from a stale plan. Add new steps, cross out abandoned ones with strikethrough, and note why.

## Keeping Tasks Small Enough to Track

If a step takes more than ~10 tool calls to complete, break it into sub-steps. Steps should be completable in a single turn or a small cluster of turns.

---

## mu agent — PLAN.md format (used by `mu agent`, not `.pi/task.md`)

When `mu agent` invokes this skill, output is a `PLAN.md` file (not `.pi/task.md`).
Follow the mu agent planner prompt exactly. Key constraints for mu agent plans:

**Test commands must be portable** — the test command runs in a plain `bash -c` subprocess
with no shell aliases. Use explicit binary names:
- `python3` not `python` (Python alias not available in non-login bash)
- `gcc` / `g++` not `cc` (more explicit)
- Always use the full command, not a Makefile alias unless a Makefile is in the plan

**No Makefile for trivial programs** — if the entire project is one source file, the Test
Command must compile and run inline. Never use `make` as the test command unless a
Makefile is explicitly listed in `## Files`.

Examples of correct trivial test commands:
- C: `gcc main.c -o main && ./main`
- Python: `python3 todo.py`
- Go: `go run main.go`
