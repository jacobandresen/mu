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

See [docs/MODELS.md](docs/MODELS.md) — recommendation, tuning, and the model-profile scheme.

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

**Where tokens go:**

- The **writer** dominates. It is multi-turn (up to 15 turns), and the later turns are mostly accumulated history rather than new instructions.
- **Skills** are about 40% of prompt tokens — a framework goal loads several, at both plan time and writer time.
- The **repair loop** re-sends the full project context plus a growing history on every iteration, so a long "still failing" run is the worst case.

**Reduction levers** (prompt management only — no change to the model, dojo, or reflexes):

- **Prompt-cache layout** (`MU_PROMPT_CACHE=1`) — put stable content (skills, rules, challenges, example) in the *system* message so LM Studio's KV cache (`cache_prompt`) reuses the prefix across writer calls; only DIR/GOAL stay volatile.
- **Selective challenge retrieval** (`MU_ENRICH_LESSONS=1`, `enrich.py`) — send only the retrieved relevant lessons instead of the whole Open section of `CHALLENGES.md`.
- *Planned:* narrow the repair context to the file(s) just changed (turns 1+), prune repair history to a sliding window, and send only the source-under-test to a test-file writer task.

## Problem-space minimization

Most of the dojo's stochasticity is **self-inflicted by the formulation**, not intrinsic to coding. With a mature reflex layer, the model-tagged data (granite n=34 pass 0.33; qwen n=32 pass 0.65) shows *no deterministic cause recurring across multiple problems* — failures are dominated by writer-stalls/degeneration. So the next lever is shrinking what the model must decide, not more reflexes.

> **A caveat that shaped the plan.** `build-rule-structure` has the highest *firing* rate for both models — but a firing means a Makefile reflex *succeeded*, not failed. (A session has one outcome, so a rate above 1-per-session can't be a failure rate.) So "fixture away the Makefile" is not the top lever: the reflexes already handle it. The real residue is degeneration and planner variance.

### Where the variance comes from

Ranked by how much each moves the outcome:

1. **The planner.** A fresh decomposition, set of filenames, and test command on every run. This is the biggest source: run a problem from a *frozen* plan and it is reproducible (5/5 with `MU_SEED`), but run it live and it swings between pass and stall.
2. **Inferred structure.** When the goal doesn't state the contract, the model invents filenames and exported symbols — each a guess.
3. **Degeneration.** The model loops or stalls. This is the model's ceiling; no reflex can reach it.
4. **Cross-file coupling.** Multi-file tasks (p7, p8, p10) add import/symbol-resolution failures.
5. **Out-of-competence runs.** Granite scores 0.0 on python/rust/go — running it there is pure noise.

### The levers

The guiding principle: **specify everything except the one thing you're measuring.** To test "can the model implement `fib()`," hand it the project, the Makefile, and the test, and ask only for the body.

- **Pin the plan** — `mu dojo measure` (shipped).
- **Provide the manifest, config, or test as a fixture** (shipped).
- **Pin filenames and the test command** — `improve-plan` (partial).
- **Route by competence** — `mu dojo run --route` (shipped).

**The minimization ladder** — a declared level per problem (`problems-catalog.json` `minimize`), each rung the one below plus a fixture:

| Level | What is given | Measures |
|---|---|---|
| **L0 open** | goal only (default) | scaffolding + structure + logic (max variance) |
| **L1 contract** | + filenames, symbols, test command in PLAN.md | structure + logic |
| **L2 scaffold** | + manifest/Makefile/config as fixtures | logic + test authoring |
| **L3 test-pinned** | + the test file as a fixture | implementation only |
| **L4 fill-in** | + impl stub with fixed signatures | function bodies only (min variance) |

L0–L1 are **capability probes** (accept variance, many rounds); L2–L4 are **logic probes** (low variance). Record each problem's level with its result — a 95%-pass at L4 isn't a 95%-pass at L0.

- **Fixture mode (L2–L4 mechanism, shipped):** `dojo/fixtures/<id>/` files are copied in and their task marked done, so the writer only fills the rest — a given file can't be written wrong. First fixture: `dojo/fixtures/p6-rust/Cargo.toml`.
- **Model-adaptive (partial):** intended to run at the declared level, **bump a rung** for mid-competence, **skip** for ≈0. Only the skip end is built (`fixtures.should_skip_problem`); auto-bump and reading the `minimize` field are planned.
- **Validation (shipped):** `mu dojo measure` reports a **stochasticity** metric (`1 − modal/N`); higher level should mean lower variance, ≈0 at L4 for an in-competence model.
