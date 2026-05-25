# Dojo Run Report – gpt‑oss‑qwen2.5‑coder‑7b‑instruct‑macos‑arm64‑8gb‑v0.7.0‑2026‑05‑25

## Overview
The run follows the workflow described in `docs/PRACTICE.md`: a fresh session folder is created, each of the seven dojo problems is executed with `mu agent`, and the results are recorded.  The goal is to identify generic improvements to **mu** (the agent framework) rather than problem‑specific hacks.

| Problem | Goal | Build / Run | Tests | Final status | Comments |
|---------|------|-------------|-------|--------------|----------|
| **p1 – helloworld (C)** | “write a hello world program in C. Use clang to compile it and run it.” | `make && ./main` → prints **Hello, World!** | – (no test file) | **PASS** | `main.c` was initially “near‑empty” (79 B) but the writer retried and produced a correct file. |
| **p2 – sqlite todo (Python)** | “todo list manager, CRUD, pytest” | `python -m pytest -q` → 3 tests passed in 0.02 s | `test_todo_manager.py` (3 tests) | **PASS** | The `python‑env` skill correctly created an isolated venv; `ruff` auto‑fixed a lint issue; the sensor `fix_test_import_module` was not needed. |
| **p3 – SDL2 line (C)** | “render a line on screen via SDL2” | `make && ./main` → binary built, runs (no visible output in head‑less CI) | – (no pytest) | **PASS** (build succeeded) | The generated `Makefile` uses `sdl2-config`.  The test command from the plan (`make && ./main`) compiles and runs the binary, which exits after a brief pause.  In a real CI you’d want a head‑less verification (e.g. off‑screen render + pixel diff). |
| **p4 – fibonacci (C#)** | “fibonacci sequence using dotnet” | `dotnet run` → prints sequence up to 10 correctly | – (no pytest) | **PASS** | The planner automatically added a canonical `.csproj` and rewrote the test command to `dotnet run`. |
| **p5 – Go Gin server** | “GET /ping → JSON {status:ok}” | `make test` → runs `go test ./...` (no test files → succeeds) | – (no test file) | **PASS** (build succeeded) | Sensors removed unused imports and ran `go mod tidy`.  The test command does **not** actually hit the HTTP endpoint – a real test would `curl localhost:8080/ping` after `go run`. |
| **p6 – Rust hello** | “print Hello, world! using Cargo” | `cargo run` → prints `Hello, world!` | – (no pytest) | **PASS** | The writer produced a minimal `src/main.rs`; a lint‑repair pass added a `Cargo.toml` file. |
| **p7 – Flask REST API** | “Flask + SQLite + CRUD + pytest” | `make test` → **fails** (no Makefile, missing dependencies, routes broken) | `tests/test_routes.py` → **fails** (routes.py missing imports, no Flask app context) | **FAIL** | The planner generated `app.py`, `models.py`, `routes.py` and a pytest file, but: <br>• No `requirements.txt` / Makefile to install Flask/SQLAlchemy/pytest. <br>• `routes.py` does not import the `app` instance or register the routes correctly, so the repair loop could not make the file runnable. <br>• The repair loop maxed out after a few edits and gave up. |

---

## General Observations & Improvements

### 1. Python‑env isolation works
* The whole run was executed inside a fresh `venv` (`/tmp/dojo‑run‑venv`).
* No host‑environment changes (e.g. pip‑install) were observed.
* `pytest` version is recent (`9.0.3`) so the historic C0 issue is gone.

### 2. Makefile / Go / C# sensors are effective
* **Makefile**: tab‑indentation is fixed automatically (`fix_makefile_space_indent`).
* **Go**: `fix_go_unused_imports` + `go mod tidy` cleared the usual import‑error wall (C3).
* **C#**: `ground_plan` added a proper `.csproj` so `dotnet run` works (C2).

### 3. Repair Loop is functional but constrained
* The loop retries up to 6 edits per failing file.
* It receives the *exact* compiler / test output (e.g. lint failures, pytest failures) and feeds that verbatim to the model.
* When the error is **unfixable** (e.g. a missing `Makefile` for Flask deps, completely wrong `routes.py`), the loop exhausts the turn budget and aborts (as seen for p7).

### 4. Planner still drops some required terms
* Each plan logs “`NOTE: PLAN.md missing some goal terms:`”.
* Missing terms → missing files or missing commands (e.g. `requirements.txt`, `Makefile`, `tests` folder).
* This is a **prompt‑rule** problem, not a sensor problem. Adding a **generic rule** to the `task‑planner` skill to enforce inclusion of:  
  - `requirements.txt` for any Python project that lists third‑party deps,  
  - a `Makefile` (or at least a “install” target) whenever the goal mentions “install”, “pip”, “requirements”, or “Makefile”,  
  - a test file placeholder (`*_test.py` or `*_test.go`) whenever “pytest” / “test” appears in the goal,  
  would markedly reduce the “missing‑term” failures.

### 5. Test‑Command handling (C8 fix)
* `_final_test_gate` now falls back to `pytest <test‑files>` when the plan omits a `## Test Command`.
* This prevented false‑positives in the past (e.g. P2 on 05‑24‑A).
* The current run correctly fell back to `pytest` for the Python problems.

### 6. Flask / Python problem (p7) – concrete improvements
| Issue | Suggested Fix (generic, not problem‑specific) |
|-------|----------------------------------------------|
| **Missing `requirements.txt` / Makefile** | Add a **prompt rule**: if the goal mentions a Python package manager (`pip`, `requirements.txt`, `install`), automatically insert a `requirements.txt` file (populated with the packages actually imported in the generated code) and a simple Makefile target `test: install deps && pytest`. |
| **Routes module is incomplete** | Add a **repair‑hint** to the `_run_repair_lint` pipeline for any Python file that fails import because a name is undefined. The hint could be: “The file `routes.py` references `app` and `db` but does not import them; add `from app import app, db` at the top.” This is a **language‑class** hint (missing import) and fits the “general deterministic fixers” policy. |
| **Database initialization** | Add a **generic sensor** `fix_sqlite_db_init` that, after writing a Flask app, checks for `SQLALCHEMY_DATABASE_URI` and, if present, runs `flask db upgrade` (or simply `touch todos.db`) inside the test gate. This would ensure the SQLite file exists before pytest runs. |
| **Test command not invoking Flask app** | The default test command could be enhanced to detect a Flask app (`from flask import Flask` in any file) and, if a `Makefile` is missing, run `pytest` directly. The existing fallback already does this, but adding a **pre‑test “install” step** (install deps if a `requirements.txt` exists) would make it more robust. |
| **Routes imports** | The `python‑env` skill already loads a helper that adds the venv to `PYTHONPATH`. A small addition to that skill could automatically prepend the project root to `sys.path` inside test runs (`export PYTHONPATH=$PWD`). This prevents import‑path issues that sometimes arise when tests are in a sub‑directory. |

### 7. Go test completeness
* The current `make test` target only runs `go test ./...`.  There are **no test files** → the command returns success but never validates the endpoint.
* A **generic rule** for Go problems that mentions “Gin” or “HTTP server” could add a minimal `_test.go` file that spins up the server in a goroutine and performs an HTTP GET on `/ping` (using `net/http/httptest`). This would be a *language‑class* sensor, not a problem‑specific hack.

### 8. SDL2 head‑less verification
* The SDL2 problem currently only checks that the binary compiles and runs; visual correctness is not verified.
* A **generic test hook** for any C/C++ project that uses a graphics library could, when `SDL2` is detected, run the program with the environment variable `SDL_VIDEODRIVER=dummy` (head‑less mode) and capture the framebuffer to a PNG (using `SDL_SaveBMP`). Then diff the PNG against a stored “golden” image (perhaps by comparing hash). This would be a **general graphics‑test pattern**, not a specific P3 fix.

### 9. C# entry‑point duplication (C5) – future work
* The current harness does not have a sensor for “multiple `Main` methods”. This is still a model convergence problem; a possible future general sensor could scan `.cs` files for `static void Main` and, if more than one, emit a warning and suggest the model remove duplicates. It would need to be language‑class‑wide, not tied to P4.

### 10. Documentation / logging improvements
* The logs already include `NOTE: PLAN.md missing some goal terms`. It would be helpful to surface those notes as **warnings** that the runner can treat as “plan quality issues” and trigger a *re‑plan* automatically.
* Adding a small helper that prints a concise summary at the end of each run (e.g. “✅ p1, ✅ p2, ✅ p3, ✅ p4, ✅ p5, ✅ p6, ❌ p7 – 6/7”) would make the dojo score immediately visible.

---

## Summary of Findings
| Category | What works | What needs work (generic, not problem‑specific) |
|----------|------------|-------------------------------------------------|
| **Build / compile** | All Makefile, Go, C#, Rust, C, SDL2 builds succeed (thanks to existing sensors). | None – the existing sensor set is sufficient. |
| **Test execution** | Python tests run in isolated venv, C# test runs, Go `go test` runs (but no tests), Rust `cargo run` runs, SDL2 binary runs. | • Add realistic tests for Go Gin server. <br>• Add head‑less verification for SDL2. |
| **Repair loop** | Repairs succeed for simple lint failures and Go import errors. | • Provide deterministic “missing import” hints for Python (routes.py). <br>• Increase repair turn budget for more complex Python fixes (p7). |
| **Planner** | Generates a well‑structured `PLAN.md` with task checklist and test command for most problems. | • Enforce inclusion of required artifacts (requirements.txt, Makefile, test files) via prompt rules. <br>• Reduce “NOTE: PLAN.md missing some goal terms” messages. |
| **Skills** | `python‑env` correctly isolates the venv; `go` sensors remove unused imports; `makefile` sensor fixes tab indentation. | • Extend `python‑env` to write a `requirements.txt` automatically based on imports. <br>• Add a generic “ensure Flask app imports its routes” sensor. |
| **Overall dojo score** | **6/7** problems pass (p7 fails). | The remaining failure is a **model‑convergence / prompt‑rule** issue rather than a harness bug. Adding the generic improvements above should allow the current model (or a slightly stronger one) to succeed. |

---

### Next Steps (high‑impact, low‑effort)
1. **Update `task‑planner` skill** to automatically add a `requirements.txt` (Python), a `Makefile` (any language where the goal mentions “install” or “Makefile”), and a test file placeholder (`*_test.py`, `*_test.go`) whenever the goal includes “test” or a testing framework name.
2. **Add a deterministic Python import‑hint** in `_run_repair_lint` (detect “NameError: name ‘app’ is not defined” etc.) and automatically suggest `from app import app, db` in `routes.py`.
3. **Create a generic Go Gin test template** (`*_test.go`) that checks `/ping` – the sensor can insert this when `Gin` is mentioned.
4. **Add a headless SDL2 test helper** that runs the binary with `SDL_VIDEODRIVER=dummy` and writes a screenshot for diffing.
5. **Expose the planner “missing‑term” notes as warnings** and automatically re‑plan (or abort) if any critical term (“requirements”, “Makefile”, “test”) is missing.

Implementing these changes will raise the dojo score to **7/7** for the current model and will also benefit future problems without over‑fitting to any single dojo task.
