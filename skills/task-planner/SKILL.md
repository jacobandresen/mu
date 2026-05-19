---
name: task-planner
description: Break down a software goal into a tracked PLAN.md with a flat task checklist and test command.
---

Write PLAN.md at the absolute path using the Write tool. No chat, no code blocks.

```
## Files
- [ ] path/to/file — description

## Test Command
<shell command, exits non-zero on failure>

## Dependencies
<compiler, libs, lint tool>
```

- Task lines MUST start with `- [ ] ` — other formats are rejected.
- List in dependency order. Name files explicitly.
- Trivial single-file: no Makefile, inline `compile && run` in Test Command.
- Multi-file or external libs: list `Makefile` first.
- Pair implementation with tests — UNLESS goal is "show/demonstrate/print"; then program execution IS the test, no separate test file.
- Never list binaries, `.db`, `.sqlite`, or runtime-generated files — source files only.
- Makefile: recipe goes tab-indented on the line AFTER `target:`. `build: gcc main.c` is WRONG (treated as prerequisites). Use `build:\n\tgcc main.c`.
- If Test Command references a make target, Makefile must define it.
- No `git push`, publish commands, or external HTTP writes in Test Command or Makefile.
- If PLAN.md exists with `[ ]` tasks, resume from the first incomplete — do not replan.
- One task = one complete file, not lines of code.
