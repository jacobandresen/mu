# Dojo

Stress-tests mu by driving a guest model through 7 fixed problems and recording where the autonomous loop breaks.

> **Honest-harness rule.** Reflexes must fix a *general class* of model error, never a specific dojo problem. A fixer that pattern-matches one problem's output measures the author's knowledge of the test, not the agent.

## Problems

| ID | Goal | Difficulty |
|----|------|------------|
| p1 | Write a hello world in C, compile with clang | trivial |
| p2 | Python todo list manager with SQLite and pytest | simple |
| p3 | Render a line via SDL2, sdl2-config in Makefile | moderate |
| p4 | Fibonacci in C#, compile with dotnet | moderate |
| p5 | Go HTTP server with Gin, GET /ping returns JSON | moderate |
| p6 | Rust CLI printing first 10 Fibonacci numbers via cargo | moderate |
| p7 | Flask REST API with SQLite, POST/GET /todos, pytest, Makefile | hard |
| p8 | Node.js todo list CLI with JSON storage, Jest tests, Makefile | simple |
| p9 | Vue 3 TypeScript todo webapp, Vite, Vitest, @vue/test-utils, Makefile | hard |
| p10 | ASP.NET Core + Vue 3 blog app, EF Core SQLite, xUnit, Vitest, seeded example post | hard |

## Running

```sh
bash sit.sh           # all 7 problems, shuffled
bash sit.sh p3-sdl2   # single problem
```

Results are written to `~/.mu/sessions/` and cleaned from `dojo/` after each run.

## Current baseline

**7/7** — qwen2.5-coder-7b-instruct, num_ctx=6000 (2026-05-30), p1–p7 only

**6/10** — qwen2.5-coder-7b-instruct, num_ctx=6000 (2026-05-31), all 10 problems

p9 newly passing (Vue 3 Vitest). p8 (Node todo) intermittent due to Jest testRegex.
p7 (Flask) and p10 (dotnet+Vue blog) model-limited — see CHALLENGES.md items 29–30.

Open challenges tracked in [CHALLENGES.md](CHALLENGES.md).

## Model / tuning

See [docs/MODELS.md](docs/MODELS.md) and [docs/TUNING.md](docs/TUNING.md).
