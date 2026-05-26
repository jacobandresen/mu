# Practice

## Dojo run

1. **Clean the dojo folder** – delete or reset `./dojo` to avoid stale artifacts.
2. **Run the dojo** – `./sit.sh`. The script will generate a fresh session in `~/.mu`.
3. **Inspect the logs** – look at the per‑problem logs under `./dojo` and the session logs under `~/.mu`.
4. **Identify weaknesses** – note repeat failures (plan parsing, sensor errors, missing tools, etc.).
5. **Apply fixes** – modify the agent code (`src/mu/…`) or the skill markdown files (`src/mu/skills/…`) as appropriate.
6. **Run the full check suite** – `make check` (which runs `mu check`, lint, and any project tests) to verify the fix does not break other parts.
7. **Bump the mu version** – update `src/mu/__init__.py` `__version__` to a new patch version (e.g. `0.9.2` → `0.9.3`).
8. **Commit the changes** – create a clear, atomic commit that references the new version (e.g. `feat: bump mu to 0.9.3 – add generic sensor for missing parens`).
9. **Record next push target** – add a line at the top of `DOJO.md` indicating the branch or remote where the next PR should be opened.
10. **Open a PR** – push the branch and open a PR using the `git-workflow` skill (or `gh pr create`), linking the PR to the updated version.

### What you can improve

**Agent code** (`src/mu/` – Python): orchestration logic, timeouts, plan validation, prompt construction, complexity detection, test normalization, sensor framework, and the iterative repair loop (`Session.repair_loop`).

**Sensors** (`src/mu/sensors.py`): add *general* deterministic fixers. Before adding a new sensor, run the **sensor test** described in `AGENTS.md` – it must be a generic language‑level fix, not specific to a single dojo problem.

**Skills** (`src/mu/skills/` – Markdown, packaged as data): the skill files shape how the LLM behaves during planning and writing. When you see a systematic model mistake, prefer a skill‑level fix over a code patch.

To improve a skill:

1. Edit the corresponding `src/mu/skills/<name>/SKILL.md` file in‑place.
2. No rebuild is required – skills are loaded at runtime via `importlib.resources`.
3. Document the change and its rationale in `findings.md`.
4. If the change alters the expected output of existing tests, add or update an automated test that demonstrates the fix.

### Standards

- **Readability** – code must be clear, idiomatic, and well‑commented.
- **Automated verification** – every change must be covered by an automated test (unit, integration, or system) that fails before the fix and passes after.
- **Linting** – run `ruff` (or the project's linter) and keep the code free of warnings.
- **Performance** – avoid unnecessary overhead; keep repair loops bounded (`_REPAIR_MAX_ITERS`).
- **Versioning** – keep `src/mu/__init__.py` in sync with Git tags and changelog entries.

### Problems

**Trivial** – single file, no external libraries:

```text
write helloworld
```

**Simple** – standard library, single file:

```text
write a python program that writes a todo entry to a sqlite3 database with a table that contains a list of todos. Create the todo table in the sqlite3 database via python. Show that the inserted entry can be read again.
```

**Moderate** – external library + Makefile:

```text
render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs.
```

**Moderate** – multi‑file project structure:

```text
write the fibonacci sequence using C#. Use the dotnet command to compile C#.
```

**Moderate** – Go HTTP server with external framework:

```text
write a Go HTTP server with a GET /ping endpoint that returns JSON {"status":"ok"}. Use the Gin framework. Include a Makefile.
```

**Moderate** – Rust CLI with Cargo:

```text
write a Rust command-line program that prints the first 10 Fibonacci numbers. Use cargo to build and run.
```

**Hard** – multi‑dependency REST API with tests:

```text
write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a "task" field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest.
```