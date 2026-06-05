# AGENTS.md

Operating guide for AI agents (and humans) working on the **mu** codebase.
mu is a local AI coding toolkit: `mu agent "<goal>"` drives an autonomous
plan → write → verify loop on top of a local LLM via LM Studio or OpenVINO.

**mu is an agent harness that employs reflexes — deterministic condition→action fixers — to repair the general classes of mistake weaker local models make.** The reflexes are *trained* in the `practice.sh` loop by stronger models: the loop runs the dojo with a weak model, distills each failure's root cause, and a stronger model (you) reads those failures and encodes a new general reflex or normalizer. Your job here is that training step.

This file is the source of truth for how to work on mu. If it conflicts with other docs, this file wins.

---

## 0. Prime directive: keep the dojo honest

The dojo runs 10 fixed problems to measure the **harness's real capability**, not to score points.

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

## 5a. Keep README.md current after dojo rounds

README.md is the front door and must hold **distilled, immediately readable knowledge** — never raw logs. After every dojo round, the problem state is reflected there:

- **Measured block (automated).** `practice.sh` rewrites the region between `<!-- DOJO-RESULTS:START -->` and `<!-- DOJO-RESULTS:END -->` at the end of *each* round with that round's per-problem PASS/FAIL. It shows **only the last round** (it overwrites, never accumulates). Do not hand-edit inside the markers.
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

## 7. Starting the inference backend

### OpenVINO (CPU/NPU — no LM Studio required)

```sh
# Start the server (loads model, serves on http://localhost:8765)
mu serve ~/.mu/models/Qwen2.5-Coder-14B-Instruct-int4-ov --port 8765 --device CPU &

# Save the backend config so mu agent routes to it automatically
python3 -c "
from mu import client
import subprocess, os
pid = int(subprocess.check_output(['pgrep','-f','mu serve']).split()[0])
client.save_backend('openvino','http://localhost:8765',
    str(client.ov_models_dir()/'Qwen2.5-Coder-14B-Instruct-int4-ov'), pid, 'CPU')
"
```

Or use the interactive picker (downloads model if needed, starts server, saves config in one step):

```sh
mu backend openvino
```

### LM Studio

Load a model in LM Studio's UI (or via `mu model`), then run `mu agent` as normal.

### Verify the backend is up

```sh
mu model warm   # prints "OpenVINO backend selected" or pings LM Studio
```
