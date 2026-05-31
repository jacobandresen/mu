# AGENTS.md

Operating guide for AI agents (and humans) working on the **mu** codebase.
mu is a local AI coding toolkit: `mu agent "<goal>"` drives an autonomous
plan → write → verify loop on top of a local LLM via LM Studio.

This file is the source of truth for how to work on mu. If it conflicts with other docs, this file wins.

---

## 0. Prime directive: keep the dojo honest

The dojo runs 7 fixed problems to measure the **harness's real capability**, not to score points.

**Do not optimize against specific dojo problems:**
- No hardcoded languages or filenames.
- A reflex is only valid if it fixes a *general class* of model error in a language or build system.
- When a problem fails, the honest fix is a general one — a better prompt rule, a general mechanism, or a better model. Never a band-aid that pattern-matches one problem's output.

---

## 1. Agent anatomy (AIMA)

mu is a learning agent with four components:

| AIMA component | mu's realization |
|---|---|
| **Performance element** | planner (`_run_planner`) + writer loop (`Session.run`) |
| **Critic** | test gate + `Session.repair_loop`; standard = "test command exits 0" |
| **Learning element** | `reflect.py` → `CHALLENGES.md`; `enrich.py` retrieves at plan time |
| **Problem generator** | the dojo (`sit.sh` / `practice.sh`) |

**Feedback path:** `AgentSession.finalize` writes the outcome → `reflect` distills failures into `CHALLENGES.md` → `enrich` retrieves lessons → `_run_planner` injects them into the next goal's system prompt.

`Session.repair_loop` is in-episode correction only — it reacts to test output within a single run and does not update the agent's knowledge base.

---

## 2. The reflex test

`reflexes.py` holds deterministic post-write fixers. Before adding one:

> **Would I write this fix for any program in this language, independent of the dojo? If "no, only because problem X needs it" — don't add it.**

**Do NOT reintroduce these removed problem-specific fixers:** SDL2 include fixers, C# `.csproj` injectors, Go `go.mod` injectors, pytest path injectors.

---

## 3. Prefer prompt rules over reflexes

When a model mistake is general to a language, the right fix is a prompt rule in `_build_autonomous_system` (`agent.py`), not a post-hoc reflex. Same honesty test applies.

---

## 4. Architecture

```
src/mu/agent.py       plan → write → lint → test → repair
src/mu/session.py     Session.run (writer) + Session.repair_loop (critic)
src/mu/plan.py        PLAN.md parsing and manipulation
src/mu/reflexes.py    deterministic post-write fixers
src/mu/tools.py       actuators (Write/Edit) + percepts (Read)
src/mu/client.py      LM Studio HTTP client
src/mu/archive.py     session tombstones + Utility record
src/mu/reflect.py     offline learner: distills failures into CHALLENGES.md
src/mu/enrich.py      retrieval: fetches relevant challenges at plan time
src/mu/lint.py        pre-execution plan critic (opt-in via MU_LINT_PLAN=1)
src/mu/__main__.py    CLI and all commands
skills/               skill prompts loaded by the planner at runtime
```

**Execution path:** Planner → Plan lint (opt-in) → Writer (one file per task) → Reflexes → Lint gate → Repair → Test gate

**Skills** (`skills/`, loaded via `_load_skill`):
- `task-planner` — defines the `PLAN.md` format for the planner.
- `python-env` — venv isolation, pytest version rules, stateless tests. Keep current; when a Python env failure recurs, add the general rule here rather than patching one problem.

---

## 5. Dojo run config

- Use the most capable model that fits in VRAM. Recommended: `qwen/qwen2.5-coder-7b-instruct` (8 GB), `mistralai/devstral-small-2507` (16 GB), or `mistralai/devstral-small-2-24b-instruct-2512` (32 GB).
- `MU_AGENT_MODEL` overrides auto-detection; default is the first model loaded in LM Studio.
- `num_ctx` default is 6000. Do not set above 8192 on M2 8 GB — causes swap and ~6× slowdown.
- Open challenges tracked in [CHALLENGES.md](CHALLENGES.md).

---

## 6. Build

```sh
make deps          # creates .venv and runs pip install -e .[dev] inside it
python3 -m mu check
```

Keep commits atomic. mu drives LM Studio via its OpenAI-compatible API (`client.py`).
