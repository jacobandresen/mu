---
name: task-planner
description: Break down a software goal into a tracked PLAN.md with a flat task checklist and test command. Use when a task has 3+ steps, will take a long time, or needs to be resumable if the session is interrupted.
---

# Task Planner

Create `PLAN.md` in the current working directory by **invoking the Write tool** with the full
absolute path. Do not emit the plan as chat text or a fenced code block — that does not create
a file. If your turn ends without a Write tool call targeting `PLAN.md`, you have failed.

## PLAN.md format

```markdown
## Files
- [ ] path/to/file — one-line description of what this file does
- [ ] path/to/test_file — unit tests for the above

## Test Command
<single portable shell command that exits non-zero on failure>

## Dependencies
- <compiler/runtime, required libraries, AND the lint tool for the language>
- Python → ruff | C/C++ → clang-tidy | Go → go vet (built-in) | Rust → cargo clippy | TypeScript → tsc | C# → dotnet format (built-in)
```

## Rules for the file list

- Every task line **must** start with `- [ ] `. Numbered lists, plain bullets, and heading-style
  tasks are rejected by downstream tooling.
- List files in dependency order: dependencies before dependents.
- Name files explicitly (`src/foo.c`, `tests/test_foo.c`, `Makefile`).
- Pair every implementation file with a unit-test file. Tests call named functions from modules,
  never `main`.
- **Exception — demonstration scripts**: if the goal is to *show* or *demonstrate* behavior
  (e.g. "write a program that X", "show that X works", "print X"), the program itself is the
  test. Do NOT add a separate unit-test file. Use program execution as the test command.
- If a build system is needed (external libraries, multi-file projects), list `Makefile` first.
- For trivial single-file programs: no Makefile, no modules — one source file only.
- **Never list auto-generated or binary output files** as write targets. This includes database files (`.db`, `.sqlite`), compiled binaries, build artifacts (`.o`, `.class`), and any file created at runtime by the program itself. Only list source files the agent must write.

## Language-specific rules

**C# / dotnet**: Every dotnet project requires a `.csproj` file. Without it, `dotnet run` and
`dotnet test` fail immediately with MSB1003. List the `.csproj` **first**, before any `.cs` files.
- Simple program: `- [ ] fibonacci.csproj` then `- [ ] Program.cs`, test command: `dotnet run --project fibonacci.csproj`
- With tests: `- [ ] src/app.csproj`, `- [ ] src/Program.cs`, `- [ ] tests/tests.csproj`, `- [ ] tests/Tests.cs`, test command: `dotnet test tests/tests.csproj`
- NEVER put `dotnet test` or `dotnet run` in Test Command unless the referenced `.csproj` appears in `## Files`.

**Rust / cargo**: Every cargo project requires a `Cargo.toml` file. Without it, `cargo build` and
`cargo run` fail immediately. List `Cargo.toml` **first** in `## Files`.
- Simple program: `- [ ] Cargo.toml` then `- [ ] src/main.rs`, test command: `cargo run`
- Binary name in test command must match the `name` field in `[[bin]]` (or defaults to the package name in `[package]`).
- Use `cargo run` or `cargo build && ./target/debug/<name>`, not `cargo build --bin main` (the binary name is not `main` unless you set it in `[[bin]]`).

**Python**: Use `python3`, never `python`. The shell subprocess has no aliases.
- When using pytest with a Makefile, the test recipe **must** use `PYTHONPATH=. pytest` (not bare `pytest`). Without this, `import app` and similar project-root imports fail with `ModuleNotFoundError` because pytest does not add the project root to `sys.path` by default.
- Test files **must import every module they use**, including stdlib modules. If a test uses `sqlite3`, add `import sqlite3` at the top. Undefined names (`F821`) cause ruff to reject the file.
- When the main module has module-level code that initializes state (e.g. creates a DB table on import), test files should import the module in a `conftest.py` fixture so the state is initialized before tests run. Do NOT open the database from tests directly without calling the setup code first.

**Go**: For projects with external packages (gin, gorilla, etc.), the Makefile must run `go mod tidy` (without suppressing errors) before building. Never silence it with `2>/dev/null || true` — a failed `go mod tidy` means the build will fail. The `go.sum` file is auto-generated; do **not** list it as a task.

**C/C++**: Use `make` when a `Makefile` is in the file list; otherwise inline: `gcc main.c -o main && ./main`.

**Makefile format**: Makefiles use tab-indented recipes under a `target:` header. This is NOT valid:
```
go mod init server
go build -o app
```
This IS valid:
```
all:
	go mod init server
	go build -o app
```
Every Makefile MUST have at least one `target:` line. Commands without a target are a syntax error.

## Rules for the Test Command

The test command runs in a plain `bash -c` subprocess with **no shell aliases**. Use explicit
binary names only:

| Wrong | Correct |
|-------|---------|
| `python script.py` | `python3 script.py` |
| `make` (with no Makefile in the file list) | `gcc main.c -o main && ./main` |
| `./binary` (graphical/interactive program) | `make` (compile-only smoke test) |
| `dotnet test` (no .csproj in file list) | `dotnet run --project app.csproj` |
| `cargo build --bin main` | `cargo run` (binary name defaults to package name, not "main") |

The test command must exit non-zero on failure. For trivial single-file programs, inline
compilation is required — compile and run in the same command.

## Internet safety

**Never** push code, publish packages, or send data to external services without explicit user
approval. This includes:
- `git push` / `gh pr create`
- `npm publish` / `pip upload` / `cargo publish`
- `curl -X POST` or any write request to an external URL
- Deploying to cloud services (Vercel, AWS, GCP, Fly, etc.)

Always stop and ask before any of these. If in doubt, ask.

## Autonomous execution

Never pause for clarification on implementation details. If a requirement is ambiguous, make the
simplest reasonable assumption and continue. Exception: anything that would publish or push data
externally — always ask first.

## When PLAN.md already exists

If `PLAN.md` is present with `[ ]` or `[~]` tasks, skip planning and resume from the first
incomplete step — do not acknowledge, do not ask, just begin.

## Keeping tasks the right size

One task = one complete file to create or modify. Never list individual lines of code as tasks.
If a step would take more than ~10 tool calls, break it into sub-steps.
