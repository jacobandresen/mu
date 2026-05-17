# Dojo Findings — claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17

## Session Summary

| Problem | Outcome | Attempts |
|---------|---------|----------|
| P1 helloworld (trivial C) | ✅ Goal complete | 1 (1 repair) |
| P2 Python SQLite | ✅ Goal complete | 4 attempts |
| P3 SDL2 line | ✅ Goal complete | 1 (1 repair) |
| P4 C# Fibonacci | ✅ Goal complete | 1 |
| P5 Go Gin HTTP server | ✅ Goal complete | 4 attempts |
| P6 Rust Fibonacci CLI | ✅ Goal complete | 1 (2 repairs) |
| P7 Flask REST API + pytest | ❌ Tests still failing | 1 attempt |

---

## Bug 1: Lint repair silently fails — `"--thinking", "auto"` is invalid

**Where:** `agent.go:runRepairLint` and the stub-retry path in the write loop

**What happened:** `runRepairLint` hardcodes `"--thinking", "auto"`. pi rejects this with:
```
Warning: Invalid thinking level "auto". Valid values: off, minimal, low, medium, high, xhigh
```
pi exits immediately, the repair does nothing. The second lint check then runs on the unchanged file.

In P7, the lint checks for `app.py` and `tests/test_todos.py` appeared to "pass after repair" — but only because ruff passed the original (syntactically valid) files. The repair protocol was broken throughout.

**Fix:** Replace `"auto"` with `"medium"` in `runRepairLint`. Also replace the `retryCfg.WriterThinking = "auto"` in stub-retries.

---

## Bug 2: Combined mode bypasses the lint gate

**Where:** `agent.go:runAgent` lines 233–241 — combined mode marks `combinedSrc` done and proceeds directly to the write loop. The write loop's lint gate runs only for files written in-loop.

**What happened (P2):** In the first three P2 attempts (combined mode = on for "simple" complexity), `todos.py` was written during the planning phase. It contained English prose embedded in Python code, causing `SyntaxError: unterminated string literal`. The lint gate (`ruff check --select=E9,F`) would have caught this immediately — but it never ran because the combined-mode file was marked done and sent straight to `finalTestGate`.

The repair loop at `finalTestGate` timed out at 220s × 3 = 660s without fixing a simple syntax error.

**Fix:** After marking `combinedSrc` done at line 241, run the lint gate on that file the same way the write loop does. If lint fails, invoke `runRepairLint` before proceeding.

---

## Bug 3: Python tests fail with `ModuleNotFoundError: No module named 'app'`

**Where:** P7 Flask session — test command `make test` → `pytest` — `tests/test_todos.py` does `import app`

**What happened:** pytest runs from the project root, but `app.py` is not on `sys.path` because pytest doesn't add `.` by default. The test collected 0 items and errored:
```
ModuleNotFoundError: No module named 'app'
```

The repair timed out at 400s without fixing this.

**Fix:** Two-pronged:
1. **skill**: Add guidance to `task-planner` skill: Python test Makefiles must use `PYTHONPATH=. pytest` or include a `conftest.py` that adds the project root to sys.path.
2. **agent code**: Add `fixPythonMakefileTest()` post-processor similar to `fixGoMakefile()` — when a Python project's `make test` target calls bare `pytest`, rewrite it to `PYTHONPATH=. pytest`.

---

## Observation: qwen3-8b is slow on complex files

P5 Go Gin (`main.go`, complex Go HTTP server) timed out on the first 3 attempts (300s writer timeout). The 4th attempt succeeded at 78s — model variance, not a systematic bug. 

The 300s WriterTimeout for "complex" is borderline for this model on this hardware (M2, 8GB RAM).

---

## Observation: "PLAN.md missing goal terms" is too noisy

The `CheckGoalAlignment` NOTE fires on nearly every problem because it flags common English verbs: "write", "using", "returns", "include", "support", "list". These are task-description words, not technical keywords. 

The word list used for alignment checking should be filtered more aggressively — at minimum skip words under 5 chars and skip verbs like "write", "using", "create", "show", "include", "returns", "support", "runs", "provide".

---

## Changes Made

- [x] Fix `"--thinking", "auto"` → `"medium"` in `runRepairLint` and stub-retry (Bug 1) — `internal/subcommands/agent.go`
- [x] Add lint gate after combined-mode file mark-done (Bug 2) — `internal/subcommands/agent.go`
- [x] Add `FixPythonMakefileTest()` for PYTHONPATH (Bug 3) — `internal/plan/parse.go` + tests in `python_test.go`
- [x] Update `task-planner` skill: Python tests need PYTHONPATH (Bug 3 skill fix) — `~/Projects/dotfiles/pi/agent/skills/task-planner/SKILL.md`
