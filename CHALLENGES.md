# Top 10 Agent Challenges

Observed across dojo sessions (qwen3:8b, qwen3:4b, gemma4:e2b) on macOS M2 8 GB.
Updated: 2026-05-21, session claude-gemma4-e2b-v0.5.0.

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

**Status:** Open. The near-empty retry (issue #6) helps recover some cases.

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

## 11. SDL2 include path: SDL.h vs SDL2/SDL.h direction varies by OS

**Symptom:** `fatal error: 'SDL2/SDL.h' file not found` on macOS or `'SDL.h' file not found` on Linux.

**Why it happens:** Homebrew SDL2 on macOS installs headers at `/usr/local/include/SDL2/SDL.h`.
The canonical include is `#include <SDL2/SDL.h>` but some models write `#include <SDL.h>`.
The sensor currently only fixes one direction.

**Impact:** P3 sensor may over-correct or under-correct depending on model output.

**Status:** Sensor covers the SDL2/SDL.h → SDL.h fix (macOS homebrew convention).
The reverse is now caught by ensuring sdl2-config --cflags is always applied.
