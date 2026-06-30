# AGENTS.md

Operating guide for AI agents (and humans) working on the **mu** codebase.
mu is a local AI coding toolkit: `mu agent "<goal>"` drives an autonomous
plan → write → verify loop on top of a local LLM via LM Studio.

**mu is an agent harness that employs reflexes — deterministic condition→action fixers — to repair the general classes of mistake weaker local models make.** The reflexes are *trained* in the `mu dojo practice` loop by stronger models: the loop runs the dojo with a weak model, distills each failure's root cause, and a stronger model (you) reads those failures and encodes a new general reflex or normalizer. Your job here is that training step.

This file is the source of truth for how to work on mu. If it conflicts with other docs, this file wins.

---

## 0. Prime directive: keep the dojo honest

The dojo runs 13 fixed problems to measure the **harness's real capability**, not to score points.

**Do not optimize against specific dojo problems:**
- No hardcoded languages or filenames.
- A reflex is only valid if it fixes a *general class* of model error in a language or build system.
- When a problem fails, the honest fix is a general one — a better prompt rule, a general mechanism, or a better model. Never a band-aid that pattern-matches one problem's output.

---

## 0a. Current focus

Where the marginal capability is, so your work lands where it moves the number:

- **Chip deterministic fruit across all thirteen problems.** A step's value is its expected gain in
  `E[N_solved]` over the whole set, ∝ logistic headroom `q(1−q)` × the chain factor — so the
  steep mid-tier problems (p2, p4, p5, p7, p8) and **broad, no-regret levers** dominate dragging the
  hardest problem. Pick a class that recurs across problems, not a one-off.
- **.NET stack (p4, p14, p15):** Structural levers already clear the build wall:
  - `MU_SCAFFOLD` + `MU_TFM_GROUNDING` + entry-point + S2 → NU1202 15→0
  - **C# reflexes** in `src/mu/reflexes/csharp/` target common compiler errors:
    `fix_csharp_missing_using`, `fix_csharp_missing_braces`, `fix_csharp_duplicate_classes`,
    `fix_csharp_lambda_brace_confusion`, `fix_csharp_package_tfm_mismatch`, and more
  - **C# LSP repair** (`MU_LSP=all`, Roslyn net10 server) — add-using fixes CS0246, organize-imports
  - `skills/dotnet-mvc` provides contract guidance (WebApplicationFactory, EF `EnsureCreated`)
  These levers combine to solve the general classes of .NET build and syntax errors. Remaining
  failures are addressed via deterministic reflexes targeting specific error patterns.
- **Prefer the LSP repair lever for the import/include/symbol classes.** `MU_LSP` drives language
  servers as a grammar-accurate repair oracle (add-include, organize-imports, add-using) — strictly
  more general than a hand-rolled regex reflex for that class, and it can't make the regex's
  scope-blind misfire. It is a *selective* lever (a fast server meeting an import failure), not a
  universal lift — see [docs/lsp.md](docs/lsp.md).
- **Measure on the board, don't assert.** Every lever is A/B'd on `mu dojo measure` / `mu dojo board`
  through honest gates; record the verdict in [docs/ablations.md](docs/ablations.md). Read null P1s
  at N=15 as *inconclusive*, not *harmful*. Full rationale: [DOJO.md](DOJO.md) (Problem-space minimization).

---

## 1. Agent anatomy (AIMA)

mu is a learning agent with four components:

| AIMA component | mu's realization |
|---|---|
| **Performance element** | planner (`_run_planner`) + writer loop (`Session.run`) |
| **Critic** | test gate + `Session.repair_loop`; standard = "test command exits 0" |
| **Learning element** | `reflect.py` → `docs/challenges/README.md`; `enrich.py` retrieves at plan time |
| **Problem generator** | the dojo (`mu dojo run` / `mu dojo practice`) |

**Feedback path:** `AgentSession.finalize` writes the outcome → `reflect` distills failures into `docs/challenges/README.md` → `enrich` retrieves lessons → `_run_planner` injects them into the next goal's system prompt.

`Session.repair_loop` is in-episode correction only — it reacts to test output within a single run and does not update the agent's knowledge base.

---

## 2. The reflex test

`reflexes/` holds deterministic post-write fixers, grouped per language. Before adding one:

> **Would I write this fix for any program in this language, independent of the dojo? If "no, only because problem X needs it" — don't add it.**

**Do NOT reintroduce these removed problem-specific fixers:** SDL2 include fixers, C# `.csproj` injectors, Go `go.mod` injectors, pytest path injectors.

---

## 3. Prefer prompt rules over reflexes

When a model mistake is general to a language, the right fix is a prompt rule in `_build_autonomous_system` (`agent.py`), not a post-hoc reflex. Same honesty test applies.

---

## 3a. Write for humans first — readable *and* modular

This code is read far more often than it is run — by the next person, and by the
weak model whose mistakes you are encoding. **Optimize for human readability and
modularity.** They are the same goal at two scales: a reader should understand
one function from its shape, and one module from its name.

**Readable (the function/line scale):**
- A reader should grasp *what* a function does and *why* from its name, docstring, and shape — without tracing control flow.
- Make the data self-describing: prefer **named** regex groups (`m['file']`) over positional ones (`m.group(1)`), small named constants over magic numbers, and a named helper over an inline lambda doing real work. `src/mu/diagnose.py` is the reference style — a table of `_rule(...)` entries each readable on its own line.
- **Reference symbols, not strings.** When one place catalogs or dispatches to code elsewhere, hold the **function/object reference**, not its name as a string — `rust.fix_rust_duplicate_use`, not `'fix_rust_duplicate_use'`. The link is then traceable (jump-to-definition, find-usages) and a rename breaks the import *immediately* instead of going silently stale. `src/mu/reflexes/registry.py` is the reference: it catalogs reflexes by direct reference, grouped by class, so the path from metadata to implementation is one click.
- Separate concerns: one function decides *what matches*, another decides *how to phrase it*; don't braid them.
- A docstring states the contract and the *why* (the failure it prevents), not a paraphrase of the code. Comments explain intent and non-obvious trade-offs, not mechanics.

**Modular (the file/package scale):**
- **One concern per module, named for it.** `reflexes/` is the reference: split per language (`python`, `rust`, `go`, …) with a `core` for the shared runner and each module carrying an explicit `__all__`. A reader finds the Rust fixers in `rust.py`, not by grepping a 3700-line file.
- **Keep modules small and cohesive.** When a file grows two unrelated responsibilities, split it (verbatim move first, prove the public API is unchanged, then evolve — see the reflexes package split).
- **Factor a shared family into a generic core + thin adapter** rather than copy-paste across toolchains (the dependency-hygiene / duplicate-declaration families — see `docs/REFLEX_KB.md` §5). The core holds the algorithm; the adapter holds the per-language table.
- **Depend in one direction:** `core` ← language modules ← package `__init__`. No lateral imports between sibling modules; shared helpers live in `core`.
- A new language or error class should be a *new small file plus a registration*, not an edit threaded through an existing large one.

**For any refactor — readability or modularity — prove behavior is unchanged** (diff old vs new output across many inputs, keep the name-set/public API identical) and say so in the commit.

Clever-but-opaque loses to plain-but-obvious every time. If a teammate would need you to explain it, rewrite it.

---

## 4. Architecture

```
src/mu/agent.py       plan → write → lint → test → repair
src/mu/session.py     Session.run (writer) + Session.repair_loop (critic)
src/mu/plan.py        PLAN.md parsing, normalizers (e.g. blocking-Go test cmd)
src/mu/reflexes/      deterministic post-write fixers, grouped per language
src/mu/diagnose.py    repair-loop sensor: distils a test/lint log to a FOCUS hint
src/mu/tools.py       actuators (Write/Edit) + percepts (Read)
src/mu/client.py      LM Studio HTTP client
src/mu/archive.py     session tombstones + Utility record
src/mu/reflect.py     offline learner: distills failures into docs/challenges/README.md
src/mu/enrich.py      retrieval: fetches relevant challenges at plan time
src/mu/lint.py        pre-execution plan linter (the lint phase of `mu improve`)
src/mu/__main__.py    CLI and all commands
skills/               skill prompts loaded by the planner at runtime
```

**Execution path:** Planner → Plan lint (opt-in) → Writer (one file per task) → Reflexes → Lint gate → Repair → Test gate

**Skills** (`skills/`, loaded via `_load_skill`):
- `task-planner` — defines the `PLAN.md` format for the planner.
- `python-env` — venv isolation, pytest version rules, stateless tests. Keep current; when a Python env failure recurs, add the general rule here rather than patching one problem.

---

## 5. Dojo run config

Model recommendation, the `MU_NUM_CTX` sweet spots, and the per-model
profile scheme live in [docs/MODELS.md](docs/MODELS.md) — the single owner;
don't restate them here. The one rule worth repeating at the point of work:
**do not load above `MU_NUM_CTX` on an 8 GB machine** (a 7B at 8048 swap-crashed
the host). Open challenges: [challenges](docs/challenges/README.md).

---

## 5z. Measuring against stochastic noise

A weak model samples tokens, so dojo results swing run to run (p7 passes, then stalls). You can't eliminate that, but don't let it fool you into "fixing" noise. Discipline:

- **Measure continuous metrics, not pass/fail.** Pass/fail is one binary sample per round. Repair-iters, first-try rate, and **tokens/call** shift smoothly and detect a real change with far fewer runs. (We caught the writer-prompt savings via prompt/call where pass/fail was pure noise.)
- **Measure multiple runs.** The planner is the dominant variance source. `mu dojo measure <id>` runs a problem N times, generating a fresh plan each run. It reports pass rate, avg repair iters, and stochasticity score.
- **N runs, compare rates — never trust one round.** `mu dojo practice --rounds 5`; read the distribution.
- **Pin the RNG for clean A/B.** `MU_SEED=<int>` (client.py) sets the seed and forces temperature 0, so identical input reproduces identical output. A *prompt* change still alters the stream, so this helps reflex/writer A/B more than prompt A/B. Unset by default (sampling surfaces diverse failures).
- **Push fixes into reflexes, not prompts.** A reflex works 100% of the time; a prompt rule only nudges a stochastic model. Converting a failure class to a deterministic reflex/normalizer removes it from the noise band entirely — the single most reliable way to cut variance.

---

## 5a. Keep README.md current after dojo rounds

README.md is the front door and must hold **distilled, immediately readable knowledge** — never raw logs. After every dojo round, the problem state is reflected there:

- **Measured block (automated).** `mu dojo practice` rewrites the region between `<!-- DOJO-RESULTS:START -->` and `<!-- DOJO-RESULTS:END -->` at the end of *each* round with that round's per-problem PASS/FAIL. It shows **only the last round** (it overwrites, never accumulates). Do not hand-edit inside the markers.
- **Curated knowledge (yours to maintain).** Outside the markers, keep current: the problem-status table's *“reflex that carries it”* column, and the **Top 3 challenges to solve**. When you add or change a reflex, update these so they stay true.
- **Always keep the run instructions** (Quick start, Commands) in README — distilling the dojo state must never remove how to run mu.
- Reflexes stay general, never problem-specific (§0).

---

## 6. Build

```sh
make deps          # creates .venv and runs pip install -e .[dev] inside it
python3 -m mu check
```

Keep commits atomic. mu drives LM Studio via its OpenAI-compatible API (`client.py`).

---

## 7. Starting LM Studio

Starting the server (`lms server start`), loading a model, and `mu check` are
in the [README quick start](README.md#quick-start). Override the host with
`MU_LMSTUDIO_HOST` if the server runs elsewhere.
