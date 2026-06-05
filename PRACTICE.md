# Practice

The dojo is how mu is trained: run the fixed problem set with a weak model, find
the general classes of mistake it makes, and encode a reflex (or normalizer) that
fixes the class. `mu dojo practice` is the loop; stronger models read the failures
and write the fixes.

## One-shot run

```sh
mu dojo run             # run all available problems once
mu dojo run p6-rust     # run a single problem
```

Inspect failures in `~/.mu/sessions/<id>/logs/`. The `diagnose` sensor
(`src/mu/diagnose.py`) distills a test/lint log into a one-line root cause.

## Training loop

```sh
mu dojo practice --rounds 3                   # repeated rounds (default 100)
mu dojo practice --rounds 1 --no-autocommit   # one round, review before commit
```

Each round:

1. Runs the full set via `mu dojo run`.
2. Appends every failed session to `dojo-failures.md`, tagged with its problem id
   and **distilled root cause** (via the diagnose sensor).
3. Reflects the round's failures into `CHALLENGES.md` (`mu reflect`).
4. Rewrites the `DOJO-RESULTS` block in `README.md` with that round's per-problem
   PASS/FAIL (last round only — it overwrites).
5. Prints a per-problem pass-rate table, worst-first.

Read the table and the distilled causes: a problem failing every round with the
**same** cause is a general class to turn into a reflex; one that varies run to
run is model quality — don't overfit it.

## Where to fix things

**Reflexes** (`src/mu/reflexes/`, grouped per language: `core`, `python`, `rust`,
`csharp`, `go`, `javascript`, `makefile`, `plan_reflexes`) — deterministic
post-write fixers, chained to a fixpoint by `run_reflexes`. Only add a reflex if
it corrects a *general* class of model error in a language or build system. The
honesty test: would you write this fix for any program in this language? If the
answer is "only because problem X needs it," don't add it.

**Planner normalizers** (`src/mu/plan.py`) — fix a recoverable plan instead of
rejecting it (e.g. `normalize_test_command` rewrites a blocking Go `./binary`
test command to `go test ./...`). A guard that can only reject fails on a model
that repeats its mistake; pair every guard with a deterministic fixer.

**Repair hints** (`src/mu/diagnose.py`) — the FOCUS line that leads the repair
prompt with the first actionable error, so a weak model edits the right file.

**Skills** (`skills/<name>/SKILL.md`) — prompt fragments injected at plan time.
Prefer a skill fix over a reflex when a better instruction would prevent the
mistake.

**Agent logic** (`src/mu/agent.py`) — orchestration, timeouts, prompt
construction, where reflexes are chained into the gates. Touch this last.

## Problems

The fixed problem set (p1–p10) and the current per-problem baseline live in
[DOJO.md](DOJO.md) — the single source. They're defined in `problems-catalog.json`.
