# Dojo Findings — claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-18

Fixes applied before this session (from -A and -B sessions):
- Removed Bash from repair tool list
- Repair prompt: prefer Edit, inject file content
- Combined planner: suppress timeout log when files already written
- CheckGoalAlignment: expanded stopwords (write/using/create/include/returns etc.)
- finalTestGate: re-apply fixCsprojTargetFramework after each repair
- recordFailedRepair / repairHistory: failed repair attempts logged to PLAN.md

## Session Summary

| Problem | Outcome | Attempts | Notes |
|---------|---------|----------|-------|
| P1 helloworld (trivial C) | ✅ Goal complete | 1 | Combined mode |
| P2 Python SQLite | ❌ Tests failing | 1 | Test doesn't init DB before querying |
| P3 SDL2 line | ✅ Goal complete | 1 | SDL include fix applied |
| P4 C# Fibonacci | ✅ Goal complete | 1 | TargetFramework fix applied |
| P5 Go Gin HTTP | ❌ Final test failed | 1 | Makefile written as plain shell script |
| P6 Rust Fibonacci | ❌ Final test failed | 1 | No Cargo.toml in plan; repair wrote invalid [bin] |
| P7 Flask REST API | ❌ Lint gate failed | 1 | `import sqlite3` missing in test file |

**Score: 3/7** (P1, P3, P4)

---

## Bug 1: Makefile written as plain shell script (P5)

**Where:** `runWriter` — writing `Makefile` for Go Gin project

**What happened:** The model wrote:
```
go mod init server

go mod tidy

go mod download gin

go build -o pinger
```
No `target:` lines. `make` fails immediately with "missing separator". `fixGoMakefile` did
nothing because `go mod` already precedes `go build` — it never checked for targets.

**Fix:** Added `fixMakefileNoTargets` — if a Makefile has no `target:` lines, wrap all commands
in a default `all:` target with tab-indented recipes. Runs before `fixGoMakefile`.

**Also:** Added skill guidance: "Every Makefile MUST have at least one `target:` line."

---

## Bug 2: Missing Cargo.toml in plan (P6)

**Where:** Planning phase — model planned `src/main.rs` only, no `Cargo.toml`

**What happened:** `cargo build --bin main && cargo run --bin main` fails without `Cargo.toml`.
The repair agent created a `Cargo.toml` but used `[bin]` instead of `[[bin]]` (invalid TOML),
causing `cargo` to error.

**Fix:** Added skill guidance: "Rust cargo projects MUST list `Cargo.toml` first in ## Files."
Also noted that `--bin main` doesn't work unless `[[bin]]` explicitly sets `name = "main"`.

---

## Bug 3: `sqlite3` not imported in Python test file (P7)

**Where:** `runWriter` — writing `tests/test_app.py`

**What happened:** Test file used `sqlite3.connect(...)` without `import sqlite3`. ruff caught
it as F821 (undefined name). Repair hit max turns (4 turns, ~37s) without fixing it.

The fix itself is trivial (add `import sqlite3`), but the repair model exhausted all turns.

**Fix:** Added skill guidance: "Test files must import every module they use, including stdlib."

---

## Bug 4: Python test design — test doesn't initialize DB (P2)

**Where:** Planning/writing — `test_todos.py` opened `todos.db` directly without calling `todos.py`

**What happened:** `todos.py` has module-level code that creates the DB table. The tests opened
`todos.db` directly and expected the table to exist, but `todos.py` was never imported or run.
All 3 tests failed with "Table 'todos' not created" / "no such table".

**Fix:** Added skill guidance: "When the main module has module-level setup code, test files
should import the module (e.g. via conftest.py) so the setup runs before tests."

---

## Observation: `--thinking off` → `/no_think` token sometimes drops

Minor: for P1 ("write helloworld") the `CheckGoalAlignment` still warns "PLAN.md contains none
of the goal keywords" because "helloworld" (compound) isn't found as "helloworld" in the plan
which says "hello world". Not a blocking issue.

## Observation: Repair model still hits max turns for simple fixes

P7's lint error (`import sqlite3` missing) is a one-Edit fix, but the repair model used all
4 turns without fixing it. This may mean the repair model returned text-only responses on some
turns. Adding more turns (4 → 6) for lint repair might help, but the root cause is the model
spending turns on analysis instead of tool calls.

---

## Changes Made

- [x] Remove animated progress bar from `session.go` (replaced with simple "Label..." line)
- [x] `fixMakefileNoTargets`: wrap shell-script Makefiles in `all:` target (Bug 1)
- [x] Skill: add Makefile format rule — must have `target:` lines (Bug 1)
- [x] Skill: add Rust cargo rule — `Cargo.toml` must be first in file list (Bug 2)
- [x] Skill: add Python import rule — test files must import all modules (Bug 3)
- [x] Skill: add Python module-level code rule — conftest.py fixture for setup (Bug 4)
- [x] `fixMakefileNoTargets` runs before `fixGoMakefile` in write loop
- [x] PRACTICE.md: removed pi references, updated to native Go loop + embedded skills

## Prioritized fixes for next session

1. **P2 test design**: skill fix should help; verify in next run
2. **P6 Cargo.toml**: skill fix should prevent missing Cargo.toml; verify in next run
3. **P7 repair max turns**: consider increasing lint repair maxTurns from 4 → 6
4. **P5 Makefile fix**: `fixMakefileNoTargets` should prevent this; verify in next run
