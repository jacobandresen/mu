# Dojo

Stress-tests mu by driving a guest model through 10 fixed problems and recording where the autonomous loop breaks.

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
bash sit.sh           # all problems, shuffled
bash sit.sh p3-sdl2   # single problem
```

Results are written to `~/.mu/sessions/` and cleaned from `dojo/` after each run.

## Current baseline

**9/10** — qwen2.5-coder-7b-instruct, num_ctx=8192 (2026-05-31), SKIP_CLEAN runs

**7/10** — qwen2.5-coder-7b-instruct, num_ctx=8192 (2026-05-31), fresh full run

- p1–p6: consistently pass
- p7: model-limited (test mixes HTTP client with ORM method; repair loop stuck)
- p8: passes on SKIP_CLEAN; stochastic on fresh plans (Jest test file naming)
- p9: passes on SKIP_CLEAN; stochastic on fresh plans (Vue compiler-sfc peer deps)
- p10: model stage passes; backend stage stochastic (C# code quality issues in repair)

### What improved (6→9/10)

| Area | Change |
|------|--------|
| Architect workflow | `mu architect` generates ARCHITECTURE.md + staged plan files for hard multi-layer problems |
| Plan parsing | `mark_task_done` handles backtick-wrapped filenames; fenced test commands extracted correctly |
| Context trimming | Lean system on writer retry; relevant_files_context capped at 3000 chars |
| Rust | Cargo.toml grounding with explicit `[[bin]]` path; duplicate-use reflex; corruption fix |
| Makefile | `\n`, `\t`, `\@`, `\$(npm)`, bare `vitest` — all normalized deterministically |
| C# | using-order fix; verbatim string escape fix; keyword-prefix artifact stripping; EF Core in csproj |
| Vue/Node | `vitest` → `vitest run` in package.json; missing `vue` peer dep added automatically |
| Repair loop | Duplicate-edit early exit; prose-response nudge; post-retry file relocation |

See CHALLENGES.md for open items.

Open challenges tracked in [CHALLENGES.md](CHALLENGES.md).

## Model / tuning

See [docs/MODELS.md](docs/MODELS.md) and [docs/TUNING.md](docs/TUNING.md).

## Token Tracking

Every dojo run records token usage to the session archive. The data is rooted in `~/.mu/sessions/<session-id>/`.

**`tokens.jsonl`** — one JSON record per LLM call:

```json
{"phase": "planner", "task_file": "", "prompt_tokens": 2134, "generated_tokens": 318, "ts": "2026-06-01T18:30:00Z"}
{"phase": "writer",  "task_file": "app.py", "prompt_tokens": 3812, "generated_tokens": 441, "ts": "..."}
{"phase": "repair",  "task_file": "", "prompt_tokens": 4201, "generated_tokens": 187, "ts": "..."}
```

Recorded phases: `planner`, `writer`, `repair`, `lint-repair`, `architect`, `stage-planner`, `split`, `flow`, `assess`, `lint-critique`.

**`meta.json`** — end-of-session summary fields added alongside the existing utility record:

```json
"total_prompt_tokens":    10147,
"total_generated_tokens": 946,
"tokens_by_phase": {
  "planner":  {"prompt": 2134, "generated": 318},
  "writer":   {"prompt": 5801, "generated": 441},
  "repair":   {"prompt": 2212, "generated": 187}
}
```

**Interpreting the data**

- High `repair` prompt share relative to `writer` means the model is generating code that fails tests; invest in prompt rules or reflexes for that language.
- High `writer` prompt share with many turns means the model is not calling the Write tool on the first try; the writer nudge loop is expensive.
- Compare `tokens_by_phase.repair.prompt` across problems to find which goals trigger the most repair work.

See [docs/token-usage-report.md](docs/token-usage-report.md) for a full analysis of where tokens go and how to reduce them.
