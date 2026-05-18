# Practice

## Setup

1. Create a working folder named after the models, hardware, version, and date:

   ```
   ./dojo/<agent-model>-<local-model>-<os>-<cpu>-<ram>[-<gpu>]-v<version>-<date>
   ```

   - `<agent-model>`: the model running this practice session (e.g. `claude`)
   - `<local-model>`: the local model under test via Ollama (e.g. `llama3`)
   - `<os>`: operating system (e.g. `macos`, `linux`, `windows`)
   - `<cpu>`: CPU identifier (e.g. `m3`, `i9-13900k`)
   - `<ram>`: total RAM (e.g. `32gb`)
   - `<gpu>`: GPU used by Ollama, omit if not applicable (e.g. `rtx4090`)
   - `<version>`: mu version from `mu version` (e.g. `v0.3.0`)
   - `<date>`: date in `YYYY-MM-DD` format

   For multiple runs on the same day, append `-A`, `-B`, `-C`, …

   Examples:
   ```
   ./dojo/claude-qwen3-8b-macos-m3-36gb-v0.3.0-2026-05-17
   ./dojo/claude-llama3-linux-i9-32gb-rtx4090-v0.3.0-2026-05-17
   ./dojo/claude-llama3-linux-i9-32gb-rtx4090-v0.3.0-2026-05-17-A
   ```
2. Write all output and findings there

## Workflow

For each problem below:

1. Run it with `mu agent`
2. Inspect the session logs in `~/.mu`
3. Identify weaknesses in the agent
4. Improve the agent code (Go source in this directory) **and/or** the skills it relies on
5. Record findings in your dojo folder

### What you can improve

**Agent code** (`internal/` — Go source): orchestration logic, timeouts, plan validation,
prompt construction, complexity detection, test normalization.

**Skills** (`skills/` — embedded Markdown): the skill files that shape how the underlying LLM
behaves during planning and writing. When you find the model consistently making the same
mistake, a skill-level fix is often more durable than a prompt patch in Go.

To improve a skill:
1. Edit it directly in `skills/<name>/SKILL.md` in this repo
2. Rebuild mu: `make build`
3. Describe the change and its rationale in `findings.md`

Skills are embedded into the mu binary at build time via `//go:embed`. No separate install step needed.

## Standards

- Code must be readable by humans
- The best solution includes an automated test that proves the problem is solved
- A good agent generates code fast

## Problems

**Trivial** — single file, no libraries:
```
write helloworld
```

**Simple** — standard library, single file:
```
write a python program that writes a todo entry to a sqlite3 database with a table that contains a list of todos. Create the todo table in the sqlite3 database via python. Show that the inserted entry can be read again.
```

**Moderate** — external library + Makefile:
```
render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs.
```

**Moderate** — multi-file project structure:
```
write the fibonacci sequence using C#. Use the dotnet command to compile C#.
```

**Moderate** — Go HTTP server with external framework:
```
write a Go HTTP server with a GET /ping endpoint that returns JSON {"status":"ok"}. Use the Gin framework. Include a Makefile.
```

**Moderate** — Rust CLI with cargo:
```
write a Rust command-line program that prints the first 10 Fibonacci numbers. Use cargo to build and run.
```

**Hard** — multi-dependency REST API with tests:
```
write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a "task" field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest.
```
