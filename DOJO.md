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
mu dojo board --runs 5             # measure ALL problems: per-layer q̂, p_solve, E[#solved]
mu dojo fixture apply p6-rust .    # copy a problem's committed fixtures into a dir
```

`measure`/`board` score each run through **honest per-layer gates** — a vacuous test log
(a build/test stage that printed nothing meaningful) does **not** count as a pass
(`_vacuous_log`/`_vacuous_pass` in `src/mu/agent.py`), so a problem's q̂ reflects real clears,
not false passes. `board` reconstructs the observed solved count from the per-layer parse as a
self-consistency check.

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

## Open problems — ranked by impact

The improvement backlog, worst-first. Evidence base: per-problem run data
(`docs/problems/p*.md`), repair-trace mining, and the `mu kb` combination report. Shipped
work is not tracked here — see git history, [docs/challenges/](docs/challenges/README.md)
for fixes, and [docs/ablations.md](docs/ablations.md) for behaviour-lever A/B verdicts.

1. **p10 full-stack (the open problem).** Multi-project C#/Vue — challenge
   [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md). Dominant errors:
   CS0101 duplicate types across files, MSB1003 no project/solution at the test dir, CS0053
   inconsistent accessibility on EF types. Mix of scaffolding (staged-plan type dedup; ensure
   `dotnet test` sees a csproj/solution) and model ceiling (cascading errors, repair
   oscillates). Biggest gap. **Lever:** template scaffolding at ground time (offline
   `dotnet new`) — SHIPPED opt-in (`MU_SCAFFOLD`); A/B verdict in
   [docs/ablations.md](docs/ablations.md) (Scaffold row).
2. **p8 jest globals** — challenge [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md).
   `describe/test/it/jest is not defined` when tests run under plain `node`. The
   package.json-script half is deterministic (`fix_package_json_bare_jest`); residual is the
   model hard-coding `node x.test.js` in a Makefile recipe — extend `fix_makefile_npm_test_jest`
   to that shape if it recurs. Remaining failures are model-ceiling module-contract bugs.
3. **p2 SQLAlchemy ORM setup** — challenge [missing-imports](docs/challenges/missing-imports.md).
   `Todo has no attribute '__table__'`, `declarative_base` undefined — declarative-base wiring
   done wrong. Candidate: a python-writer skill rule, or a reflex for the standard
   declarative-base shape.
4. **p9 component/test contract** — challenge [incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md).
   Assertion mismatches (component renders heading + button, not the todo text). Mostly model
   quality — low priority, accept variance.

## Token tracking

Every run records token usage to the session archive. `tokens.jsonl` holds one record per
LLM call (`phase`, `task_file`, `prompt_tokens`, `generated_tokens`, `ts`); `meta.json` adds
`total_prompt_tokens`, `total_generated_tokens`, and `tokens_by_phase`, which the session
summary and the reflex KB (`mu kb`) read.

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
`mu dojo measure` (pin the plan + report a `1 − modal/N` stochasticity metric), the whole-set
`mu dojo board`, fixture mode (`dojo/fixtures/<id>/` files copied in and marked done), and
competence routing (`fixtures.should_skip_problem`). Template scaffolding (the general L2
mechanism) is SHIPPED opt-in (`MU_SCAFFOLD`, [`src/mu/scaffold.py`](src/mu/scaffold.py));
verdict in [docs/ablations.md](docs/ablations.md).

**Why broad levers over the hardest problem.** The target is to raise
`E[N_solved] = Σ_i P_i` across the whole set, not p10 in isolation. A step's marginal value
on problem *i*, layer *ℓ* scales as the *logistic headroom* `q(1−q)` times the *chain factor*
`∏_{ℓ′≠ℓ} q_{ℓ′}` (clearing one layer only helps if the siblings also clear). For p10 every
layer sits at q≈0, so both factors ≈0 — a step there buys almost nothing; a mid-tier problem
at q≈0.5 with healthy siblings buys far more. So prefer **broad, no-regret levers** (honest
gates, cross-stage reflexes, organize-imports/LSP) and the **steep mid-tier** problems first;
treat p10/.NET as the frontier, invested in only via levers that also help others. The .NET
ladder (p10/p13/p14) is now judged **model-ceiling-bound for qwen-7b** — the structural levers
clear the build wall but the residual is model semantics — so deterministic effort goes to the
non-.NET problems. Full lever verdicts and that conclusion: [docs/ablations.md](docs/ablations.md).
