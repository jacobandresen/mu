# Dojo Session — claude-2026-05-17

## Problem 1: Trivial — `write helloworld`

### What happened

Combined-mode planner produced PLAN.md with `make` as Test Command, but no Makefile
in the file list and no Makefile on disk. `main.c` was correct C.

Final test gate ran `make` → exit 2. Repair agent started.

Repair agent session (from JSONL evidence):
1. Ran `make` → "No targets specified and no makefile found." (exit 2)
2. Wrote a dummy Makefile whose `all` target echoes "No targets specified" and exits 0
3. Ran `make` → "No targets specified" (exit 0) — tests technically pass here
4. But agent saw the text "No targets specified" and re-wrote the same Makefile
5. Repeated steps 3-4 **8+ times** over 13+ minutes — never stopped

Root causes:
- `runRepair` has **no timeout** — calls `cmd.Run()` and blocks forever
- Harness delegates pass/fail judgment to the model, which misread exit-0 output text
- Combined planner ignored "no Makefile, inline compilation" prompt constraint

### Bugs

| # | Description | Severity |
|---|---|---|
| 1 | `runRepair` has no timeout — hangs indefinitely if model loops | Blocker |
| 2 | Combined planner outputs `make` as test command with no Makefile in file list | High |
| 3 | Repair harness lets model interpret exit codes (text-based stop condition) | High |
| 4 | `CheckGoalAlignment` false positive on "helloworld" vs "hello world" | Low |

### Fixes

1. **`runRepair` timeout + harness polling**: mirror `runWriter` ticker pattern. Every
   2s harness runs test command silently. If exit 0, kill pi. If WriterTimeout elapses,
   kill pi. Harness is the judge, not the model.

2. **`plan.FixNoMakefileTestCommand`**: after any planner run, if TestCommand == "make"
   and no Makefile is in the task list, rewrite to inline compile derived from file
   extension (e.g. `gcc main.c -o main && ./main`).

---

## Problem 2: Simple — Python SQLite3 todo

### What happened

Planner classified task as `complexity=complex` (word count >8 triggers complex despite
being a single stdlib file). Used separate planner + writer sessions (~124s + ~126s).

`todo.py` was correct and ran fine with `python3 todo.py`. But PLAN.md test command
was `python todo.py`. Test ran in a `bash -c` subprocess with no shell aliases — `python`
not found → exit 1.

All 3 repair retries launched but each timed out after 240s. The repair agent cannot
fix a missing binary by editing code — a structural mismatch between what's broken and
what the repair agent knows how to do.

### Bugs

| # | Description | Severity |
|---|---|---|
| 5 | Word count >8 triggers `complexity=complex`; verbose goals for simple tasks get wrong class | Medium |
| 6 | Test command `python` fails in bash subprocesses (not a real binary, only a shell alias) | High |
| 7 | Repair agent cannot distinguish "wrong code" from "wrong binary name" — wastes all retries | Medium |

### Fixes

3. **Remove word count from complex trigger** (`detectComplexity`): only external
   libraries (libRE match) should trigger complex. Word count ≤4 stays trivial, else
   simple. Verbose descriptions of simple tasks no longer over-budget.

4. **`plan.NormalizeTestCommand`**: after planner, replace `python ` → `python3 ` in
   the test command so it works in non-login bash subprocesses. Applied before
   `FixNoMakefileTestCommand`.

### pi SKILL improvement

Updated `task-planner/SKILL.md` in dotfiles (skills-v1.1):
- Added portability rules: `python3` not `python`, no bare `make` for trivial programs
- Internet safety section: no push/publish/external POST without approval
- Works standalone without mu agent

---

## Problem 2 continued: Writer empty-content failure

### What happened

After fixing the word-count and python3 issues, the writer still failed to produce `todos.py`.
Session JSONL showed model generated 228 output tokens but `content: []` — empty content.
The model was generating thinking tokens only and stopping without a tool call.

Comparison with a working manual pi invocation (test at `/tmp/mu-test-writer/`) revealed the
only prompt difference: the mu agent's `buildWritePrompt` includes a `## What good looks like`
section with `Wrong: ...` examples. The manual test prompt did NOT have this section.

Hypothesis: the negative examples ("Wrong: ...") cause qwen3:ralph to enter an extended
deliberation about what "wrong" looks like, consuming the full context budget on thinking tokens
without ever reaching a tool call.

### Bug

| # | Description | Severity |
|---|---|---|
| 8 | `## What good looks like` in write prompt causes qwen3:ralph to generate ~228 thinking tokens and stop without calling Write | High |

### Fix

5. **Remove `## What good looks like` section** from `buildWritePrompt`: keep only `## Steps`
   (concise 3-step instructions). Negative examples trigger over-deliberation in the model.
   Removing them restored writer to reliably calling Write in ~66s.

### Outcome

Simple problem now passes end-to-end:
- `todos.py` written in 66s
- Repair agent fixed a Python syntax error (f-string `\n` inside braces, invalid <3.12)
- Final tests passed after repair

---

## Problem 3: Moderate — SDL2 line rendering

### What happened

First try success. Planner correctly identified `main.c` + `Makefile`. Writer wrote both files.
mu agent auto-fixed `#include <SDL2/SDL.h>` → `#include <SDL.h>` (macOS homebrew path).
Test command `make` compiled cleanly. No repair needed.

Times: plan=50s, main.c=40s, Makefile=14s.

---

## Problem 4: Moderate — Fibonacci C# with dotnet

### What happened

Planner produced `src/FibonacciProgram.cs` + `tests/FibonacciTests.cs` with `dotnet test`.
No `.csproj` files in the plan. `dotnet test` fails immediately:

```
MSBUILD : error MSB1003: Specify a project or solution file.
```

Repair agent looped writing `FibonacciTests.cs` 8+ times (same content each time) — it
interpreted the MSBuild error as a code error and rewrote the C# file, which changed nothing.
Repair timed out after 300s.

Root cause: planner doesn't know that `dotnet test` requires `.csproj` project files.
The repair agent cannot fix missing infrastructure (project files) by rewriting source code.

### Bugs

| # | Description | Severity |
|---|---|---|
| 9 | Planner generates `dotnet test` without `.csproj` files — MSBuild can't find project | High |
| 10 | Repair agent loops on infrastructure errors (missing project files) just like it looped on `make` — model can't distinguish "wrong code" from "missing build system" | High |

### Fix

6. **task-planner skill**: Add dotnet-specific guidance: C# projects using `dotnet` MUST
   include a `.csproj` file. For simple programs, prefer `dotnet run` over `dotnet test`.
   For test projects, include both `app.csproj` and `tests.csproj` in the file list.

### pi SKILL improvement

Updated `task-planner/SKILL.md` to add dotnet section:
```
C# / dotnet: every project needs a .csproj file. List it before the .cs files.
For single-file programs: one .csproj + one Program.cs, test command: dotnet run.
For test suites: list app.csproj, src/*.cs, tests.csproj, tests/*.cs — test command: dotnet test.
```
