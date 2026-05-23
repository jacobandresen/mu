# Top 16 Agent Challenges

Observed across dojo sessions (qwen3:8b, qwen3:4b, gemma4:e2b) on macOS M2 8 GB.
Updated: 2026-05-22, runs 6+I (FixOrphanTopLevelCommands duplicate-all bug; reapplyMakefileFix coverage gap).

> **2026-05-22 — sensors intentionally removed.** Most problem-specific sensors documented
> below as "Fix landed" were deliberately removed to keep the dojo honest: a sensor that
> pattern-matches one exact dojo problem (SDL3→SDL2 API swap, pip-install injection, .csproj
> TargetFramework, Cargo.toml repair, go.mod fixes, SQLite/Flask scaffolding) measures the
> harness author's knowledge of the test, not the agent's capability. The Go plan-generator
> (which hardcoded the 5 test languages and the problem filenames) was removed for the same
> reason. **Only general, language-class fixes remain**: Makefile syntax repair (tabs,
> targets, recipes) and Python syntax repair (multiline strings, missing parens, test-import
> names, ruff autofix). The entries below are kept as a historical record of failure patterns
> that small models exhibit — treat "Fix landed" as "was tried", not "currently active".

---

## 1. Repair agent does not call tools (gemma4:e2b)

**Symptom:** Repair phase generates 600–1200 tokens of natural language on turn 1, then emits
single-token responses (gen=1) on turns 2–4 and never calls Write. Max-turns reached every time.

**Why it happens:** gemma4:e2b appears to treat the repair system prompt as a conversation
rather than a tool-use task. The model explains what it would do instead of doing it.

**Impact:** P2, P3, P4 all failed because the model wrote correct analysis but never issued the Write tool call.

**Status:** Open. Mitigation: expand sensor coverage so fewer problems need repair at all.

---

## 2. SQLite table not created at import time

**Symptom:** `sqlite3.OperationalError: no such table: todos` when tests import the module.

**Why it happens:** Model places `initialize_db()` / `create_table()` inside `if __name__ == '__main__'`.
When pytest imports the module directly that block never runs.

**Impact:** P2 (SQLite todo manager) failed all 3 runs.

**Partial fix landed:** `FixSQLiteInitDb` sensor.
**Remaining bug:** `strings.Index(content, "initialize_db()")` matched the function DEFINITION `def initialize_db():` because `initialize_db()` is a substring of `initialize_db():`. Sensor returned early thinking the call existed at module scope.
**Fix applied:** Now searches for `"\n" + funcName + "()"` (unindented standalone call) to distinguish definition from call site. Also added test-file guard to skip `test_*.py` files.

---

## 3. Makefile defines SDL_CFLAGS but does not use it

**Symptom:** `fatal error: 'SDL.h' file not found` even though SDL2 is installed.

**Why it happens:** Model writes `SDL_CFLAGS=$(sdl2-config --cflags)` as a variable but omits it
from the compile command. The include path is never passed to the compiler.

**Impact:** P3 (SDL2) compile fails silently; repair can't help if repair agent won't call tools.

**Fix landed:** `FixMakefileSDL2` sensor appends `$(shell sdl2-config --cflags)` to CFLAGS.

---

## 4. .csproj file written with markdown syntax instead of XML

**Symptom:** MSBuild error: `'Project' start tag does not match end tag of 'TargetFramework'`.

**Why it happens:** gemma4:e2b mixes markdown formatting (`##PropertyGroup>`, `[Project Sdk=...]`)
into XML. The file is unparseable by MSBuild.

**Impact:** P4 (Fibonacci C#) failed — the project file was garbage.

**Fix landed:** `FixCsprojMarkdownCorruption` detects `##` tags and replaces the whole file
with a clean SDK template.

---

## 5. Python Makefile missing pip install step

**Symptom:** `ModuleNotFoundError: No module named 'flask'` when pytest collects tests.

**Why it happens:** Model writes a Makefile with a `test:` target that calls pytest directly,
forgetting to install dependencies first — even when the goal explicitly says "install with pip".
Sometimes the model creates a separate `pip_install:` target but doesn't make `test:` depend on it.

**Impact:** P7 (Flask REST API) fails at the test stage.

**Fix landed:** `FixMakefilePipInstall` adds a pip install step before the pytest invocation,
but only if pip install doesn't already appear immediately before pytest in the same recipe.
**Remaining bug in run 2:** When the model wrote `pip install -r requirements.txt` in a separate
`pip_install:` target, the sensor returned early seeing "pip install" anywhere in the file.
**Fix applied:** Now checks only if pip install appears as a preceding recipe line in the same
target block as pytest.

---

## 6. Writer produces near-empty files (< 100 bytes)

**Symptom:** Log line `Writer produced near-empty X (N bytes) — retrying with thinking`.

**Why it happens:** Model generates only a few tokens — often just the filename or a brief comment —
before stopping. Most common on simple files where the model may interpret "write a hello world" literally.

**Impact:** Requires a retry with elevated thinking, adding 10–15 s per occurrence.

**Status:** Handled by existing retry-with-thinking logic. Occurs ~1–2× per dojo run.

---

## 7. Test file calls wrong method names (API mismatch)

**Symptom:** `AttributeError: module 'todo' has no attribute 'add_item'` — test calls `add_item`
but implementation defines `add_todo`.

**Why it happens:** The test is written before or independently of the implementation, and the
model picks different names. Without reference context, the test and impl diverge.

**Impact:** Repair needed; if repair agent fails (issue #1), problem fails.

**Fix landed:** Reference-file context injected into retry prompts with a CRITICAL note to
use exact method names.

---

## 8. go.mod has hallucinated package versions

**Symptom:** `go: github.com/gin-gonic/gin@v2.0.0: invalid version`

**Why it happens:** Model invents plausible-sounding but non-existent version numbers.

**Impact:** `go build` fails; requires repair or sensor correction.

**Fix landed:** `FixGoModVersions` replaces hallucinated versions with known-stable pins.

---

## 9. Model generates tokens but never calls a tool in writer phase

**Symptom:** Multiple chat turns (gen=1367, gen=708, gen=1), then "Writer did not produce X".

**Why it happens:** gemma4:e2b generates a long explanation of what it will write, then runs out
of context or generates an end-of-sequence token instead of a tool call. Distinct from issue #1
(repair) — this happens even in the primary write phase for complex files like test_todo.py.

**Impact:** Extra retry cycle needed; if retries also fail, task is abandoned.

**Fix landed (2026-05-21, run 4):** Code-block extraction in `session.go`. When the model
returns prose with no tool calls in writer mode and the target file doesn't exist, the agent
now extracts the first fenced code block matching the file's extension and writes it directly.
This recovers the content the model wrote as prose without an extra LLM round-trip.

---

## 10. Test file imports wrong module name

**Symptom:** `ModuleNotFoundError: No module named 'todo_manager'` when only `todo.py` exists.

**Why it happens:** The model writes the implementation as `todo.py` (matching the PLAN) but then
names the import in the test `from todo_manager import ...`. No module named `todo_manager` exists.

**Impact:** All test collection fails immediately; P2 fails at import time.

**Fix landed:** `FixTestImportModule` scans `from X import ...` lines in test files, checks if
`X.py` exists on disk, and if not, finds a candidate `.py` file whose name overlaps with X
(prefix/suffix/substring match). Renames the import to the actual file.

---

## 11. Model uses SDL3 API (SDL_DestroySurface) in SDL2 code

**Symptom:** `error: call to undeclared function 'SDL_DestroySurface'` at compile time.

**Why it happens:** gemma4:e2b was trained on mixed SDL2 and SDL3 code. `SDL_DestroySurface` is
the SDL3 API; SDL2 uses `SDL_FreeSurface`. The model produces SDL3-style surface cleanup code
even when the goal and Makefile explicitly reference SDL2.

**Impact:** P3 (SDL2) regressed from ✓ (run 2) to ✗ (run 3) when this new API variant appeared.

**Fix landed:** `FixSDLDestroySurface` sensor replaces `SDL_DestroySurface(` with `SDL_FreeSurface(`.

---

## 12. Makefile recipe uses spaces instead of tabs

**Symptom:** `Makefile:N: *** missing separator. Stop.`

**Why it happens:** The model writes recipe lines indented with spaces (e.g. 4 spaces) instead of
a tab character. This happens even when there IS a target line — so `FixNoTargets` (which handles
the "no targets at all" case) doesn't fire.

**Impact:** P7 (Flask) Makefile was syntactically invalid despite having a correct target structure.

**Fix landed:** `FixMakefileSpaceIndent` sensor detects space-indented recipe lines within target
blocks and converts them to tab indentation. Runs first in the sensor chain before `FixNoTargets`.

---

## 14. Makefile has orphan commands before the first target

**Symptom:** `Makefile:N: *** missing separator. Stop.` even after `FixMakefileSpaceIndent`.

**Why it happens:** The model declares `.PHONY: all test clean` and individual targets (`test:`,
`clean:`) but writes the `all:` target's recipe as bare commands at the top level, BEFORE any
target definition. For example:
```
.PHONY: all test clean

pip install -r requirements.txt    ← orphan (no target, no tab)
pytest test_todo.py               ← orphan (no target, no tab)

test:
    pytest test_todo.py
```

`make` sees `pip install -r requirements.txt` as a directive, not a recipe, and fails.
`FixNoTargets` doesn't fire (file has targets). `FixMakefileSpaceIndent` doesn't fire (no spaces, no indentation at all).

**Impact:** P7 Makefile broken on Run 4 with this exact pattern.

**Fix landed:** `FixOrphanTopLevelCommands` collects bare command lines outside any target block
and wraps them in a new `all:` target. Wired after `FixMakefileSpaceIndent`, before `FixNoTargets`.

---

## 13. SDL2 include path: SDL.h vs SDL2/SDL.h direction varies by OS

**Symptom:** `fatal error: 'SDL2/SDL.h' file not found` on macOS or `'SDL.h' file not found` on Linux.

**Why it happens:** Homebrew SDL2 on macOS installs headers at `/usr/local/include/SDL2/SDL.h`.
The canonical include is `#include <SDL2/SDL.h>` but some models write `#include <SDL.h>`.
The sensor currently only fixes one direction.

**Impact:** P3 sensor may over-correct or under-correct depending on model output.

**Status:** Sensor covers the SDL2/SDL.h → SDL.h fix (macOS homebrew convention).
The reverse is now caught by ensuring sdl2-config --cflags is always applied.

---

## 15. FixOrphanTopLevelCommands creates a duplicate `all:` target

**Symptom:** `Makefile:N: warning: overriding commands for target 'all'` + `No rule to make target 'X', needed by 'all'.`

**Why it happens:** `FixOrphanTopLevelCommands` prepends a new `all:` target for orphan commands, but
when the model ALSO writes an explicit `all:` target below the orphans, the result has two `all:` targets.
`make` treats the second as an override, which either silently uses the wrong recipe or errors on GNU make.
Example trigger: model writes bare gcc lines then `.PHONY: all` + `all: prog` + `prog: ...`.

**Impact:** P3 (SDL2) — initial `make` fails on first `finalTestGate` attempt, triggering unnecessary repair
cycles that then revert working Makefile content.

**Fix landed:** `FixOrphanTopLevelCommands` now checks if `clean` already contains an `all:` target.
If yes, it prepends orphan recipe lines INTO the existing `all:` recipe instead of creating a second target.

---

## 16. `reapplyMakefileFix` only re-applied 2 of 8 write-phase sensors

**Symptom:** After repair, `make` fails with `missing separator`, `SDL.h not found`, or duplicate targets —
even though the same failures were fixed by sensors during the initial write phase.

**Why it happens:** The repair model frequently rewrites the Makefile entirely, reverting every sensor
fix that was applied during the write phase. `reapplyMakefileFix` (called before each `finalTestGate`
attempt) only re-applied `FixPytestPath` and `FixGoMakefile`, leaving 6 other sensors unrun.

**Impact:** P3 (SDL2) — after 1–2 repair attempts the Makefile reverts to bare commands with no target
and no SDL2 wiring. Subsequent test runs all fail with the same structural error.

**Fix landed:** `reapplyMakefileFix` now runs the full write-phase sensor set: SpaceIndent,
OrphanTopLevelCommands, NoTargets, InlineRecipe, DuplicateVar, SDL2, PipInstall, GoMakefile,
PythonMakefileTest, and PytestPath.
