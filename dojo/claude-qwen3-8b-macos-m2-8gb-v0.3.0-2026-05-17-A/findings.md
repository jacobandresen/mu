# Dojo Findings — claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17-A

First run of the native Go Ollama loop (pi removed). Baseline for the new implementation.

## Session Summary

| Problem | Outcome | Notes |
|---------|---------|-------|
| P1 helloworld (trivial C) | ✅ Goal complete | Combined timeout noise; files written correctly |
| P2 Python SQLite | ❌ Lint gate failed | `import pytest` unused; lint repair returned text, no tool call |
| P3 SDL2 line | ✅ Goal complete | 1 attempt; SDL2 include fix applied |
| P4 C# Fibonacci | ❌ Final test failed | Repair loop reverted .csproj to net8.0; max turns reached ×3 |
| P5 Go Gin HTTP | ❌ Final test failed | Unused `fmt` import; repair loop hit max turns ×3 |
| P6 Rust Fibonacci | ❌ Repair regression | Repair fixed `mut` but introduced `println!=` syntax error |
| P7 Flask REST API + pytest | ❌ Wrong tests + lint repair | Writer wrote wrong tests; `import pytest` unused; repair hit max turns |

Score: **2/7** (P1, P3)

---

## Bug 1: Repair model returns text without calling a tool (silent no-op)

**Where:** `runRepairLint` and `runRepair` — any repair session with `watchFile=""`

**What happened (P2):** Lint repair was called for `import pytest` unused (ruff F401). The
session returned with no tool_calls — the model wrote a text response explaining the fix
instead of calling Write or Edit. The file was unchanged; lint still failed; agent exited.

**Root cause:** In the native Go loop, the model can respond with text (no tool_calls) and
`session.Run` returns `true, nil` (success). The harness re-runs lint, finds it still failing,
and exits. There is no enforcement that the model MUST use a tool.

**Fix candidates:**
- If a repair session returns 0 tool calls, treat it as a failure and retry
- Strengthen the repair system prompt: "You MUST call Write or Edit. Text responses are failures."

**Status:** Partially addressed — repair prompt now says "Call Write or Edit exactly once".
The text-only response mode was not re-triggered after the fix (P6/P7 used turns, not silence).

---

## Bug 2: Repair model calls Bash despite "do NOT run any commands" instruction

**Where:** `runRepairLint` and `runRepair` — repair sessions with Bash in the tool list

**What happened (P4, P5 pre-fix):** Repair sessions hit "max turns reached" at ~64-80s for
all 3 retry attempts. Pattern: model calls Bash to re-run the test command, writes a fix,
runs Bash again to verify, loops.

**What happened (P6, P7 post-fix):** After reducing maxTurns to 4 and adding "do NOT run
any commands", repair sessions still take ~35s/turn (consistent with Bash calls). P6 took 34s
for 4 turns; P7 repair took 142s for 4 turns. The model is still calling Bash.

**Root cause:** The repair system prompt says "do NOT run any commands" but the Bash tool is
still in the tool list. The model ignores the text instruction and calls Bash anyway.

**Fix candidate (decisive):** Remove Bash from the tool list in repair sessions. If only
Write/Edit/Read are available, the model cannot run commands regardless of instructions.

---

## Bug 3: Repair model uses Write (full rewrite) for lint fixes, introducing new errors

**Where:** `runRepairLint` — repair for single-file lint errors

**What happened (P6):** Lint error: `cannot assign twice to immutable variable` (missing `mut`).
Repair model called Write, rewrote the file, fixed `mut` — but also changed `println!("{}")` to
`println!="{}")` (broken macro syntax). Lint failed again with a different error. Second repair
attempt also hit max turns. Net result: the file is worse than the original.

**Root cause:** Repair prompt says "Call Write or Edit exactly once" — model chooses Write
(full rewrite), not Edit (targeted). A full rewrite of a file the model hasn't seen in context
can introduce new errors.

**Fix candidates:**
- Change repair prompt: "Call Edit to make the smallest targeted change. Do not rewrite the file."
- Consider injecting the current file content into the repair prompt so the model edits from truth

---

## Bug 4: Repair loop worsens state (P4 C#)

**Where:** `finalTestGate` → `runRepair` multiple times

**What happened (P4):** `fixCsprojTargetFramework` correctly patched `net8.0` → `net10.0`.
`finalTestGate` ran `dotnet run` (reason for initial failure unclear — possibly output noise).
Repair model called Bash to run `dotnet run`, saw `net8.0 not found`, then rewrote
`fibonacci.csproj` with `net8.0` (doesn't know installed version). After 3×10 turns, the
.csproj was stuck on net8.0. Manual test with net10.0 passes immediately.

**Fix candidates:**
- Inject installed dotnet version into repair prompt context
- Re-run `fixCsprojTargetFramework` after each repair attempt (simple harness fix)

---

## Bug 5: Writer model ignores the spec for complex test files (P7)

**Where:** `runWriter` — writing `tests/test_app.py`

**What happened (P7):** Task asked for `GET /items` and `POST /items` tests. The writer model
wrote `test_homepage()`, `test_about()`, `test_contact()`, `test_api()`, `test_database()` —
none of which test the specified endpoints. The test file was also a ruff lint fail
(`import pytest` unused, `from flask import Flask` unused).

**Root cause:** The writer model has only the PLAN.md and the file path as context. The PLAN.md
listed the correct file names but the model appears to have written generic Flask tests from
training data rather than reading the spec from PLAN.md.

**Fix candidates:**
- Inject the original task goal into the writer system prompt (not just the skill)
- Include the PLAN.md content in the writer user prompt, not just the file path

---

## Observation: Combined planner timeout fires harmlessly

**Where:** `runCombinedPlanner` — P1 and P2

**What happened:** The combined session timeout fires after files are already written. The
last Chat() call (model's "I'm done" turn) takes longer than the remaining budget, returning
a context deadline exceeded error. Files are present; agent continues correctly.

The error log message is confusing but the behavior is correct. Could suppress the log when
the target files were successfully written.

---

## Observation: `CheckGoalAlignment` NOTE fires on every problem

P1–P7 all triggered NOTE: "PLAN.md is missing some goal terms." Common task-description
verbs and short words flagged as missing technical keywords. Not a blocking issue but noisy.
Pre-existing from the last session, tracked in ollama_direct.md item #8.

---

## Changes made during this session

- [x] Reduced `maxRetries` in `finalTestGate` from 3 → 1 (immediate, addresses user request)
- [x] Reduced `maxTurns` in repair sessions from 10 → 4
- [x] Repair prompt: added "do NOT run any commands, call Write or Edit exactly once"

## Prioritized fixes for next session

1. **Remove Bash from repair tool list** (Bug 2) — decisive fix, 1-line change in agent.go
2. **Change repair prompt to prefer Edit** (Bug 3) — "Call Edit to make the smallest targeted change"
3. **Inject goal into writer prompt** (Bug 5) — writer model ignores spec without goal in context
4. **Suppress combined planner timeout noise** (Observation) — log only when files are missing
