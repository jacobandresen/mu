# Practice

## Dojo workflow

1. Run `bash sit.sh` — all 7 problems, shuffled.
2. Inspect failures in `~/.mu/sessions/<id>/logs/` and `PLAN-final.md`.
3. Identify the error class (lint, test isolation, missing dep, model error).
4. Apply the fix — see below.
5. Re-run and confirm the problem flips pass → pass without regressing others.
6. Commit with a clear message.

## Where to fix things

**Reflexes** (`src/mu/reflexes.py`) — deterministic post-write fixers. Only add a reflex if it corrects a *general* class of model error in a language or build system. Apply the honesty test: would you write this fix for any program in this language? If the answer is "only because problem X needs it," don't add it.

**Skills** (`skills/<name>/SKILL.md`) — prompt fragments injected at plan time. Prefer a skill fix over a reflex when the model makes a systematic mistake that a better instruction would prevent.

**Agent logic** (`src/mu/agent.py`) — orchestration, timeouts, prompt construction. Touch this last.

## Problems

| ID | Difficulty | Goal |
|----|------------|------|
| p1-helloworld | trivial | Write a hello world in C, compile with clang |
| p2-sqlite | simple | Python todo list with SQLite, add/list/delete, pytest |
| p3-sdl2 | moderate | Render a line via SDL2, sdl2-config in Makefile |
| p4-fibonacci | moderate | Fibonacci in C#, compile with dotnet |
| p5-gin | moderate | Go HTTP server with Gin, GET /ping → `{"status":"ok"}` |
| p6-rust | moderate | Rust CLI printing first 10 Fibonacci numbers via cargo |
| p7-flask | hard | Flask REST API, SQLite, POST/GET /todos, pytest, Makefile |
