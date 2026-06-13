# Dojo

Stress-tests mu by driving a guest model through 10 fixed problems and recording where the
autonomous loop breaks. The problem set, per-problem detail, and the last round's result
live in **[docs/problems/](docs/problems/)**; recurring failure classes in
**[docs/challenges/](docs/challenges/README.md)**.

> **Honest-harness rule** ([AGENTS.md §0](AGENTS.md)). A fix — reflex or tool — must address
> a *general class* of model error, never a specific dojo problem.

## Running

`mu dojo …` (equivalently `python -m mu.dojo …`); every subcommand has `--help`.

```sh
mu dojo run                        # all available problems, shuffled
mu dojo run p3-sdl2                # a single problem
mu dojo run --route --model M      # skip problems M is measured hopeless on
mu dojo practice --rounds 5        # repeated rounds: run, distill, reflect, repeat
mu dojo measure p7-flask --runs 5  # N runs, fresh plan each; reports pass rate + stochasticity
mu dojo fixture apply p6-rust .    # copy a problem's committed fixtures into a dir
```

Results land in `~/.mu/sessions/<id>/`; `dojo/` is cleaned after each run (committed
`dojo/fixtures/` spared). Env knobs work as flag defaults (`ROUNDS`, `MU_SEED`, `MU_ROUTE`,
`SKIP_CLEAN`, …). Inspect a failure in `~/.mu/sessions/<id>/logs/`; `diagnose`
(`src/mu/diagnose.py`) distils a test/lint log into a one-line FOCUS cause.

## Training loop

`mu dojo practice` is how mu is trained: run the set with a weak model, find the general
classes of mistake, encode a reflex or normalizer for the class. Each round:

1. Runs the full set (`mu dojo run`).
2. Distils the round's failures into `docs/challenges/README.md` (`mu reflect`), each tagged
   with its diagnose cause.
3. Rewrites the visual result block in `docs/problems/README.md` (last round only).
4. Prints a per-problem pass-rate table, worst-first.

Read the table with the causes: a problem failing every round on the **same** cause is a
general class to fix; one that varies run to run is model quality — don't overfit it.

## Where to fix things

In rough order of preference (and see [AGENTS.md](AGENTS.md) §2–4 for the honesty test):

- **Skills** (`skills/<name>/SKILL.md`) — a prompt fragment that *prevents* the mistake.
- **Planner normalizers** (`src/mu/plan.py`) — repair a recoverable plan rather than reject
  it; pair every guard with a deterministic fixer.
- **Reflexes** (`src/mu/reflexes/`, per language) — deterministic post-write fixers chained
  to a fixpoint by `run_reflexes`. General class only.
- **Repair hints** (`src/mu/diagnose.py`) — the FOCUS line leading the repair prompt.
- **Agent logic** (`src/mu/agent.py`) — orchestration and gates; touch last.

External tools (formatters, type checkers, scaffolders) as an alternative to bespoke
reflexes are surveyed in [TOOLS.md](TOOLS.md). Model choice and tuning: [docs/MODELS.md](docs/MODELS.md).

## Token tracking

Every run records token usage to the session archive. `tokens.jsonl` holds one record per
LLM call (`phase`, `task_file`, `prompt_tokens`, `generated_tokens`, `ts`); `meta.json` adds
`total_prompt_tokens`, `total_generated_tokens`, and `tokens_by_phase`. `mu token-report`
aggregates them into `token_usage.md`.

The **writer** dominates (multi-turn, accumulating history); skills are ~40% of prompt
tokens; the **repair loop** re-sends project context plus a growing history each iteration,
so a long "still failing" run is the worst case. A high `repair`-to-`writer` ratio means the
model generates code that fails tests — invest in reflexes/prompt rules for that language.
Prompt-management levers (no model/dojo change): `MU_PROMPT_CACHE=1` (stable content in the
system message for KV-cache reuse) and `MU_ENRICH_LESSONS=1` (send only retrieved relevant
lessons, not the whole Open section).

## Problem-space minimization

Most dojo stochasticity is **self-inflicted by the formulation**, not intrinsic to coding —
the dominant residue is planner variance and degeneration, not a recurring deterministic
cause. So the next lever is shrinking what the model must decide, on a declared **minimization
ladder** (`problems-catalog.json` `minimize`), each rung the one below plus a fixture:

| Level | What is given | Measures |
|---|---|---|
| **L0 open** | goal only (default) | scaffolding + structure + logic (max variance) |
| **L1 contract** | + filenames, symbols, test command in PLAN.md | structure + logic |
| **L2 scaffold** | + manifest/Makefile/config as fixtures | logic + test authoring |
| **L3 test-pinned** | + the test file as a fixture | implementation only |
| **L4 fill-in** | + impl stub with fixed signatures | function bodies only (min variance) |

Guiding principle: **specify everything except the one thing you're measuring.** L0–L1 are
capability probes (accept variance, many rounds); L2–L4 are logic probes (low variance).
Record each problem's level with its result — a 95%-pass at L4 is not one at L0. Shipped:
`mu dojo measure` (pin the plan + report a `1 − modal/N` stochasticity metric), fixture mode
(`dojo/fixtures/<id>/` files copied in and marked done), and competence routing
(`fixtures.should_skip_problem`). Template scaffolding (the general L2 mechanism) is planned —
[docs/plans/scaffolding.md](docs/plans/scaffolding.md).
