# Plan: port the dojo shell scripts to Python

> **STATUS: implemented (2026-06-05).** The three `.sh` scripts are deleted; the
> rig lives in `src/mu/dojo/`. One deviation from the plan below: instead of
> staying at `python -m mu.dojo`, the rig was promoted to a hidden `mu dojo`
> subcommand with a real argparse CLI (flags + `--help`), per a follow-up
> request — `python -m mu.dojo …` still works identically. This file is kept as
> the historical design record.

Rewrite `measure.sh`, `sit.sh`, and `practice.sh` (619 lines of bash) as a small,
readable Python package. The scripts already shell out to Python/awk for every
non-trivial step — parsing `meta.json`, distilling causes, rewriting README — so
the bash is mostly glue around mu's own modules. Porting removes the
bash→awk→heredoc layering and lets the rig call `mu.toolchain`, `mu.diagnose`,
`mu.fixtures`, and the session archive directly.

## Guiding principle: this is the test rig, not the product

The shipped CLI surface (`mu plan|agent|iterate|architect|reflect|kb|…`) was
deliberately trimmed. The dojo rig is **harness, not product**, so it stays off
that surface. It lives under `python -m mu.dojo …`, matching the existing
`python -m mu.fixtures` idiom — no new top-level `mu` subcommands, and
`__main__.py` (937 lines) is left untouched.

```
python -m mu.dojo measure  p9-vue-todo          # was: ./measure.sh
python -m mu.dojo run       [problem-id]         # was: ./sit.sh
python -m mu.dojo practice                       # was: ./practice.sh
```

## Module layout — `src/mu/dojo/`

Each module is one responsibility, small enough to read top-to-bottom. Shared
helpers are extracted so `measure` and `practice` stop duplicating session-scan
and PATH logic.

| Module | Replaces | Responsibility |
|---|---|---|
| `__init__.py` | — | package marker + short module docstring |
| `__main__.py` | — | `python -m mu.dojo <run\|measure\|practice>` dispatch (argparse, mirrors fixtures.py CLI) |
| `env.py` | PATH/export blocks | `augment_path()`, archive dir, LM Studio host, num-ctx defaults — one place |
| `sessions.py` | `find … meta.json` + awk | `SessionMeta` dataclass + `sessions_since(marker_time)`; `root_cause(dir)` reusing `diagnose.distill_test_errors` |
| `runner.py` | `sit.sh` | `run_problem()` / `run_all()`: toolchain filtering, competence routing, fixture apply, agent invocation |
| `measure.py` | `measure.sh` | freeze golden plan, N runs from it, pass-rate + avg-repair + stochasticity |
| `readme.py` | awk block surgery | `refresh_dojo_results()` — rewrite the `<!-- DOJO-RESULTS -->` block |
| `practice.py` | `practice.sh` | rounds loop, digest, reflect, token-report, scoped autocommit, barren/empty tracking, lock, timeout |

### Readability choices (the point of the rewrite)

- **Dataclasses over positional `|`-joined strings.** `meta.json` becomes a
  `SessionMeta(outcome, goal, session_id, project_dir, repair_iters)` read with
  `json.load`, not `awk -F'"'`. The `outcome|pid` temp files disappear — they
  become lists of `SessionMeta`.
- **`pathlib` + `Counter`** replace `mktemp`/`find`/`ls -t`/`sort -n|cut`. The
  per-problem worst-first summary is a `collections.Counter` + `sorted(key=…)`,
  readable as one comprehension instead of an awk program.
- **Reuse, don't re-shell.** `root_cause()` imports `distill_test_errors`
  directly (the `_root_cause` heredoc); routing/fixtures call `mu.fixtures`
  directly (no `python -m` round-trip); catalog loading uses
  `mu.toolchain.load_problems_catalog` / `available`.
- **Docstrings carry the *why*** the current comments hold (e.g. why the marker
  uses `-newer`, why README overwrites instead of accumulating, why empty rounds
  count as barren). The explanations are an asset — port them verbatim into
  docstrings.

## Cross-cutting design decisions

- **Subprocess for `agent`/`iterate`, in-process for everything else.** The
  per-problem agent call stays a subprocess (`mu agent …` / `mu iterate …`):
  it preserves crash isolation and lets `practice`'s per-round `timeout` cleanly
  kill a hung run. All parsing, scanning, README/digest writing, and the rounds
  loop are in-process Python.
- **Lock:** `flock` → `fcntl.flock` on an open fd, same graceful fallback when
  unavailable (warn, continue).
- **Round timeout:** `subprocess.run(..., timeout=ROUND_TIMEOUT)` around the
  `run` call, catching `TimeoutExpired` (replaces `timeout --foreground`).
- **Config via env, parsed once.** Keep every `ROUNDS=`, `N=`, `MU_SEED=`,
  `SKIP_*=`, `MU_ROUTE=` knob working (muscle memory + existing docs), read in
  `env.py`/argparse. argparse flags may *also* be offered, but env stays the
  contract.

## PARITY REQUIREMENTS (named, not incidental)

1. **Best-effort `|| true` semantics.** The scripts swallow failure almost
   everywhere: warm-up, the `sit.sh`/round invocation, `reflect`,
   `token-report`, autocommit, the timeout. Each optional step must be wrapped
   in `try/except` with a logged skip. A naive port that lets one failed
   `reflect` propagate would abort a 100-round run hours in — the regression
   would only surface mid-run. This is a requirement, not a nicety.
2. **Identical artifacts.** Same `dojo-failures.md` digest format, same
   `DOJO-RESULTS` block (markers, date/model line, numeric `p1..p10` sort,
   worst-outcome-wins collapse), same `token_usage.md`, same `measure` summary
   line.
3. **Identical control flow.** barren vs empty round tracking, two-empty bail,
   `STOP_AFTER_BARREN`, scoped `git commit -o` touching only
   README/CHALLENGES/token_usage.
4. **Golden plans / fixtures / catalog untouched.** `dojo/golden/*/PLAN.md`,
   `dojo/fixtures/**`, `problems-catalog.json` are inputs, not rewritten.

## Phasing — validate each by side-by-side artifact diff

Unit tests won't really cover I/O orchestration; the real check is old-vs-new on
the same input, diffing the artifacts. Keep the `.sh` files until the diffs match.

- **Phase 0 — shared.** `env.py`, `sessions.py` (+ `SessionMeta`, `root_cause`).
  Unit-test `sessions_since` against a fixture archive; confirm `root_cause`
  matches `_root_cause` on a few real session logs.
- **Phase 1 — `measure`** (smallest, self-contained). Folds in the `outcomes`
  unbound-var fix already made to `measure.sh`. Validate: same summary line as
  `measure.sh` on the frozen `p9-vue-todo` golden plan, `MU_SEED` pinned.
- **Phase 2 — `run`** (`sit.sh`). Validate single-problem and all-problems runs:
  same skip notices, same routing/fixture behavior, sessions land in the archive
  identically.
- **Phase 3 — `practice`.** Validate `ROUNDS=1 SKIP_AUTOCOMMIT=1`: diff the
  produced `dojo-failures.md` section and the README `DOJO-RESULTS` block against
  a `practice.sh` run on the same archive state.
- **Phase 4 — cut over.** Update `README.md`, `AGENTS.md`, `PRACTICE.md`,
  `DOJO.md` to the `python -m mu.dojo` commands; delete the three `.sh` files
  (or leave 2-line shims that `exec python -m mu.dojo …` for muscle memory).
  Add an AGENTS readability note that the rig lives in `mu.dojo`.

## Risks

- **Behavior drift** in barren/empty logic and autocommit scoping — covered by
  Phase 3 artifact diff.
- **README marker edge cases** (missing block, empty round) — `readme.py` must
  no-op exactly where the awk did.
- **Hidden `set -e` reliance** — bash aborts on the next unguarded failure;
  Python won't. Parity requirement #1 is the mitigation.

## Out of scope

The sampler/degeneration experiment in flight (`measure.sh` on p9) and any reflex
or fixture changes. This is a faithful port: same behavior, readable in Python.
