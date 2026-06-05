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

The dojo rig is a hidden `mu` subcommand (`mu dojo …`, equivalently `python -m mu.dojo …`). Every command has `--help`.

```sh
mu dojo run                        # all available problems, shuffled
mu dojo run p3-sdl2                 # a single problem
mu dojo run --route --model M      # skip problems M is measured hopeless on
mu dojo practice --rounds 5        # repeated rounds: run, distill, reflect, repeat
mu dojo measure p7-flask --runs 5  # N runs from a frozen plan (isolates writer variance)
mu dojo fixture apply p6-rust .    # copy a problem's committed fixtures into a dir
```

Results are written to `~/.mu/sessions/` and cleaned from `dojo/` after each run (committed `dojo/golden/` and `dojo/fixtures/` are spared). The long-standing env knobs still work as flag defaults — `ROUNDS`, `N`, `MU_SEED`, `MU_ROUTE`, `SKIP_CLEAN`, etc.

Inspect failures in `~/.mu/sessions/<id>/logs/`; the `diagnose` sensor (`src/mu/diagnose.py`) distills a test/lint log into a one-line root cause.

## Training loop

`mu dojo practice` is how mu is trained: run the set with a weak model, find the general classes of mistake it makes, encode a reflex (or normalizer) that fixes the class. Each round:

1. Runs the full set via `mu dojo run`.
2. Appends every failed session to `dojo-failures.md`, tagged with its problem id and **distilled root cause** (the diagnose sensor).
3. Reflects the round's failures into `CHALLENGES.md` (`mu reflect`).
4. Rewrites the `DOJO-RESULTS` block in `README.md` with that round's PASS/FAIL (last round only — it overwrites).
5. Prints a per-problem pass-rate table, worst-first.

Read the table and the causes: a problem failing every round with the **same** cause is a general class to turn into a reflex; one that varies run to run is model quality — don't overfit it.

## Where to fix things

- **Reflexes** (`src/mu/reflexes/`, per language: `core`, `python`, `rust`, `csharp`, `go`, `javascript`, `makefile`, `plan_reflexes`) — deterministic post-write fixers, chained to a fixpoint by `run_reflexes`. Only add one for a *general* class. Honesty test: would you write this fix for any program in this language? If "only because problem X needs it," don't.
- **Planner normalizers** (`src/mu/plan.py`) — fix a recoverable plan instead of rejecting it (e.g. `normalize_test_command` rewrites a blocking Go `./binary` test to `go test ./...`). Pair every guard with a deterministic fixer — a guard that only rejects fails on a model that repeats its mistake.
- **Repair hints** (`src/mu/diagnose.py`) — the FOCUS line that leads the repair prompt with the first actionable error, so a weak model edits the right file.
- **Skills** (`skills/<name>/SKILL.md`) — prompt fragments injected at plan time. Prefer a skill when a better instruction would prevent the mistake.
- **Agent logic** (`src/mu/agent.py`) — orchestration, timeouts, where reflexes chain into the gates. Touch this last.

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
