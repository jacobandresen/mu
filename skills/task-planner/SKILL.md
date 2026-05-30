---
name: task-planner
description: Break down a software goal into a tracked PLAN.md with a flat task checklist and test command.
---

Output ONLY a task list. Do NOT write file contents or code.

REQUIRED format — copy this structure exactly:
```
## Files
- [ ] path/to/file — one-line description

## Test Command
<shell command that exits non-zero on failure>

## Dependencies
<compiler, libs, tools>
```

Rules:
- Every task line starts with `- [ ] ` (dash space bracket space bracket space). No other prefix.
- Do NOT include file contents, code blocks, or implementation details.
- Do NOT use `### filename` headers — list format only.
- Do NOT use numbered lists.
- List in dependency order. Name all source files explicitly.
- Trivial single-file: no Makefile, inline `compile && run` in Test Command.
- Multi-file or external libs: include Makefile.
- Pair implementation with tests unless goal says "show/print" (then program output IS the test).
- Never list binaries, `.db`, `.sqlite`, or runtime-generated files.
- Makefile recipes must be tab-indented on the line AFTER `target:`.
- If Test Command references a make target, Makefile must define it.
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

## Additional Generic Rules (auto‑added by the planner)
- **Python projects**: when the goal references third‑party Python packages (e.g. mentions `Flask`, `SQLAlchemy`, `requests`, or any import not in the standard library), automatically add a `requirements.txt` file listing those packages (un‑pinned) and a simple `Makefile` target `install:` that runs `python -m venv .venv && .venv/bin/pip install -r requirements.txt`. The test command should use the venv (`.venv/bin/pytest`).
- **Makefile requirement**: if the goal mentions any of `install`, `pip`, `requirements`, `make`, or `Makefile`, ensure a `Makefile` is listed as the first task and contains at least an `install` (or `test`) target appropriate for the language (e.g. `install:` for Python, `build:` for C/Go). This prevents missing‑term failures.
- **Test file placeholder**: when the goal contains the words `test`, `pytest`, `unittest`, `go test`, or mentions a testing framework (e.g. `Gin` with `GET /ping`), automatically add a test file stub (`*_test.py` for Python, `*_test.go` for Go, etc.) with a minimal skeleton that the model can flesh out. The test file should be listed as a task and the test command should invoke the appropriate test runner (e.g. `pytest` or `go test`).
- **Go HTTP servers MUST use `go test ./...`** — NEVER `./main` or `make && ./main`. `./main` starts a blocking server process that never exits; the test gate hangs forever. Always pair a Go HTTP goal with a `*_test.go` file and set:
  ```
  ## Test Command
  go test ./...
  ```
  Do NOT write `make && ./main` or `./main` for any Go project whose binary is a long-running server.
