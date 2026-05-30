# AGENTS.md

Operating guide for AI agents (and humans) working on the **mu** codebase.
mu is a local AI coding toolkit: `mu agent "<goal>"` drives an autonomous
plan → write → verify loop on top of a local LLM via LM Studio.

This file is the source of truth for *how to work on mu*. If it conflicts with
older docs (e.g. `README.md`), this file wins.

---

## 0. Prime directive: keep the dojo honest

The `dojo/` benchmark runs 7 fixed problems (helloworld C, SQLite Python, SDL2 C,
fibonacci C#, Go/Gin, Rust, Flask). Its purpose is to measure the **agent
harness's real capability** at driving a small local model — not to score points.

**Do not optimize the harness against the specific dojo problems.** Concretely:

- **No hardcoded languages.** Don't add `if lang == "python":` that bakes in the
  test languages. The LLM planner produces `PLAN.md`; the model decides file names.
- **No problem-specific reflexes.** A deterministic fixer is only allowed if it
  corrects a *general class* of model error in a language or build system.
- **When a dojo problem fails, the honest fix is a general one:** a better model
  choice, a better *generic* prompt rule, or a general mechanism — never a
  band-aid that pattern-matches that one problem's output.

---

## 1. Agent anatomy (AIMA)

mu is a **learning agent** in the AIMA sense. Its four components:

| AIMA component | What it does | mu's realization |
|---|---|---|
| **Performance element** | Selects and executes actions from percepts | planner (`_run_planner`) + writer loop (`Session.run`) |
| **Critic** | Judges actions against a fixed performance standard | test gate + `Session.repair_loop`; standard = "test command exits 0" |
| **Learning element** | Uses critic feedback to improve the performance element | `reflect.py` (TELLs the KB) + `enrich.py` (ASKs the KB) |
| **Problem generator** | Manufactures fresh experience for the learner | the dojo (`sit.sh` / `practice.sh` / `dojo/`) |

**PEAS:**
- **Performance measure:** `pass` (test exits 0), `first_try_pass`, `repair_iters`, `wall_seconds`, `tasks_done`. Recorded per session in `meta.json` as `archive.Utility`.
- **Environment:** project working directory + host toolchains + LM Studio. Partially observable, stochastic (LLM), sequential, single-agent.
- **Actuators:** `tools._write`, `tools._edit`, `tools._bash` — the only ways mu changes the world.
- **Percepts:** `tools._read` + captured gate stdout/stderr — the only way mu observes the world.

**The feedback path** (how learning happens across episodes):
`AgentSession.finalize` writes the `Utility` record → `reflect` distills failed sessions into `CHALLENGES.md` → `enrich` retrieves relevant lessons at plan time → `_run_planner` injects them into the next goal's system prompt.

**In-episode correction** (`Session.repair_loop`) is a *model-based reflex* — it reacts to test output within a single run and does not change the agent. Across-episode learning is the critic→learner path above.

**AIMA role aliases** (Stage 2): `mu.learner` → `mu.reflect`, `mu.recall` → `mu.enrich`, `mu.memory` → `mu.archive`. Set in `mu/__init__.py`; physical renames ship after tests cover these paths.

---

## 2. The reflex test

`mu/reflexes.py` holds deterministic, model-free fixers applied after a file
is written. (`mu/sensors.py` is a backward-compat shim that re-exports
everything from `reflexes.py`; prefer `mu.reflexes` in new code.) Before
adding or keeping a reflex, apply this test:

> **Would I write this exact fix for any program in this language/build system,
> independent of the dojo? If the answer is "no, only because problem X needs
> it," the reflex is overfit — don't add it.**

**Allowed (general language-class fixes):**

| Area | Reflex | Why it's general |
|------|--------|------------------|
| Makefile | `fix_makefile_space_indent` | Make *requires* tab-indented recipes |
| Makefile | `fix_orphan_top_level_commands`, `fix_no_targets`, `fix_inline_recipe`, `fix_duplicate_var` | General Makefile syntax repair |
| Python | `fix_multiline_single_quote`, `fix_missing_close_paren` | General Python syntax errors |
| Python | `fix_test_import_module` | Test imports a module name not on disk — general |
| Python | `py_autofix` | Strips unused imports/variables via autoflake; a general linter |

**Removed (problem-specific) — do NOT reintroduce:**
SDL2 include/API fixers, C# `.csproj` fixers, Go `go.mod` fixers, pytest path
fixers, pipeline-specific `pip install` injectors. These encoded one dojo problem.

---

## 3. Prefer generic instructions over reflexes

When the model makes a mistake that *is* general to a language, the right fix is
usually a **prompt rule in `_build_autonomous_system`** (in `mu/agent.py`),
not a post-hoc reflex. A prompt rule teaches the model to get it right the first
time.

**Rule for prompt additions: same honesty test as reflexes.**

---

## 3.5 The v0.3 lesson: a general iterative loop beats reflexes

The highest dojo score ever recorded is **v0.3 (2026-05-17): 6/7** — higher than
every reflex-laden version since. What it had was **an iterative repair loop** that
could run the test command, read the failure, edit, re-run, and iterate until green.

**Implemented in v0.7.0:** `Session.repair_loop` in `mu/session.py` does exactly
this — a single repair conversation where the *harness* runs the test after each
edit (deterministic) and feeds the new output back to the model, looping up to
`_REPAIR_MAX_ITERS` until green.

---

## 4. Architecture (where things live)

```
src/mu/agent.py       agent program: plan → write → lint → test → repair
src/mu/session.py     performance element (Session.run) + critic (Session.repair_loop)
src/mu/plan.py        problem representation: PLAN.md parsing and manipulation
src/mu/reflexes.py    simple-reflex layer: deterministic effectors (post-write)
src/mu/sensors.py     backward-compat shim → re-exports mu.reflexes
src/mu/tools.py       actuators (Write/Edit/Bash) + percepts (Read)
src/mu/client.py      reasoning-engine interface: LM Studio HTTP client
src/mu/archive.py     episodic memory: session tombstones + Utility record
src/mu/reflect.py     learning element (offline): TELLs CHALLENGES.md
src/mu/enrich.py      learning element (retrieval): ASKs the archive
src/mu/lint.py        pre-execution plan critic (a-priori, form only)
src/mu/__main__.py    CLI (argparse) and all commands
src/mu/skills/        background knowledge: skill prompts loaded by the planner
```

`mu agent` is a deterministic control plane composing model sessions:

- **Planner** (`_run_planner`) → LLM produces `PLAN.md` (Files, Test Command, Dependencies)
- **Plan lint** (`mu/lint.py`, opt-in via `MU_LINT_PLAN=1`) → deterministic
  warnings (entity consistency, vague verbs, pronouns, underspec) fed back to
  the planner for one revision pass; spaCy optional, regex fallback. `mu lint`
  runs the checks standalone with no LLM.
- **Writer** (`_run_writer`) → one file per task; tools restricted to Write/Edit
- **Reflexes** (`mu/reflexes.py`) → general deterministic fixes post-write
- **Lint gate → Repair → Test gate → Final test gate** → `Session.repair_loop` injects test output between edits
- **Plan hygiene** (`mu/plan.py`) → general normalizers only

### Skills (`src/mu/skills/`, packaged data, loaded via `_load_skill`)

- **`task-planner`** — injected into the planner system prompt; defines the
  `PLAN.md` format.
- **`python-env`** — environment and test-tooling rules for Python work
  (venv isolation, matching pytest to the interpreter, compatible dependency
  pins, stateless tests, import-safe modules). **Apply it whenever you generate,
  debug, or repair Python that installs packages or runs pytest** — these are the
  rules behind the C0 failure class (broken pytest, dep skew) on P2/P7; see
  `docs/DOJO.md`. Keep it current: when a Python tooling/env failure recurs,
  record the general rule there rather than patching one problem.

---

## 5. Dojo workflow & run config

- Each run lives in `dojo/`.
- open challenges an where to push next is tracked in `docs/DOJO.md`.
- **Bias success over speed:** use the most capable model that fits.
  Recommended: `qwen/qwen2.5-coder-7b-instruct` (8 GB) or `mistralai/devstral-small-2507` (16 GB).
- Model is selected via `MU_AGENT_MODEL` or auto-detected from the first model loaded in LM Studio.
- Connection errors retry up to 2× with 5-second backoff (`chat_or_retry` in `mu/client.py`).

---

## 6. Build / test

```sh
make deps          # pip install -e . (installs lmstudio and httpx)
make install       # pip install -e .
python3 -m mu check
```

- Keep commits focused and atomic.
- Don't add documentation files unless asked.
- mu drives LM Studio via its OpenAI-compatible API (`mu/client.py`).
