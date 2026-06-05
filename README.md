# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai) or [OpenVINO](https://docs.openvino.ai) (CPU inference, no GPU required).

**mu is an agent harness that employs *reflexes* — deterministic, condition→action fixers — to repair the mistakes weaker local models make.** A small model (e.g. a 3B) writes plausible but broken code: an invalid `Cargo.toml` dependency, a test that forgets to import `app`, a Makefile recipe without a tab, a Go test command that blocks forever. Each reflex corrects one *general class* of such error before the lint/test gate runs, so a weak model lands working code far more often than its raw output would allow.

**The reflexes are trained in the `practice.sh` loop by stronger models.** `practice.sh` runs the dojo repeatedly with a weak model, distills the root cause of every failure, and surfaces the chronic ones; a stronger model (the developer, or an LLM agent like Claude) then reads those failures and encodes a new general reflex or normalizer. Over rounds, the harness accumulates the fixes a weak model can't make for itself. Reflexes must fix a *general* class — never a specific dojo problem.

**Requires:** Python 3.11+, and one of:
- **LM Studio** running at `localhost:1234` (default), or
- **OpenVINO GenAI** (`pip install openvino openvino-genai`) with a converted model

## Quick start

```sh
git clone https://github.com/jacobandresen/mu
cd mu
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
source .venv/bin/activate

# Start LM Studio, load a model, start the server
mu check                          # verify dependencies
mu toolchain                      # show installed compiler toolchains
mu setup                          # install missing toolchains (interactive)
mu agent "write a Flask REST API with SQLite and pytest tests" --dir myproject
```

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop |
| `mu architect "goal"` | Generate ARCHITECTURE.md and staged plan files for hard multi-layer problems |
| `mu plan "goal"` | Generate PLAN.md only (no code writing) |
| `mu iterate` | Continue executing an existing PLAN.md |
| `mu split` | Split broad plan tasks into smaller, actionable files |
| `mu flow` | Pair each plan task with a testable step |
| `mu assess` | Assess each plan task for goal alignment |
| `mu check` | Verify all dependencies are installed |
| `mu toolchain` | Show status of all compiler toolchains |
| `mu toolchain check` | Exit 1 if any toolchain is missing (CI-friendly) |
| `mu setup` | Interactively install missing toolchains |
| `mu model` | Browse and select LM Studio models |
| `mu model load <id>` | Load a model (LM Studio or OpenVINO) |
| `mu backend openvino` | Switch to OpenVINO inference backend |
| `mu backend lmstudio` | Switch back to LM Studio backend |
| `mu serve [model_dir]` | Start a local OpenVINO-backed OpenAI-compatible server |
| `mu clean` | Report large files |
| `mu extract <log>` | Salvage files from an agent session log |
| `mu lint [PLAN.md]` | Report deterministic plan warnings (no LLM) |
| `mu reflect` | Distil recent failed sessions into CHALLENGES.md |
| `mu version` | Print mu version |

## Toolchains

`mu toolchain` shows which compiler toolchains are installed and what each dojo problem requires. `mu setup` presents a checklist of missing toolchains and installs only what you select — it never upgrades tools that are already present.

| Toolchain | Binary | Language |
|-----------|--------|----------|
| `clang` | `clang` | C / C++ |
| `go` | `go` | Go |
| `cargo` | `cargo`, `rustc` | Rust |
| `dotnet` | `dotnet` | C# |
| `python3` | `python3` | Python |
| `node` | `node`, `npm` | JavaScript / TypeScript |
| `sdl2` | `sdl2-config` | SDL2 graphics |

**LM Studio** is not a toolchain — download it from [lmstudio.ai](https://lmstudio.ai), load a model, and start the local server. mu connects to `http://localhost:1234` by default (override with `MU_LMSTUDIO_HOST`).

## OpenVINO (CPU inference, no GPU required)

mu can run inference entirely on CPU via [OpenVINO GenAI](https://docs.openvino.ai/latest/openvino_docs_OV_UG_supported_plugins_CPU.html) — no LM Studio or GPU needed.

**Install dependencies:**
```sh
pip install openvino openvino-genai
```

**Convert a model to OpenVINO IR** (using [Optimum Intel](https://github.com/huggingface/optimum-intel)):
```sh
pip install optimum[openvino]
optimum-cli export openvino --model Qwen/Qwen2.5-Coder-7B-Instruct --weight-format int4 ./models/qwen2.5-coder-7b
```

**Start the server** (uses half the available CPU threads by default):
```sh
mu serve ./models/qwen2.5-coder-7b
```

**Switch mu to the OpenVINO backend:**
```sh
mu model load ./models/qwen2.5-coder-7b --backend openvino
# mu now routes all agent commands to the OpenVINO server automatically
```

**Switch back to LM Studio:**
```sh
mu backend lmstudio
```

Run `mu check` to see the status of both backends at any time.

## Recommended models

| VRAM | Model | Notes |
|------|-------|-------|
| Any | `ibm/granite-4.1-3b` | **Primary.** IBM Granite 4.1 3B; ~2 GB; 128K context; native tool calling; fits Raspberry Pi |
| 8 GB | `qwen/qwen2.5-coder-7b-instruct` | Code specialist; 88.4% HumanEval; 92+ languages |
| 16 GB | `mistralai/devstral-small-2507` | 53.6% SWE-bench; agentic coding; 128K context |
| 32 GB | `mistralai/devstral-small-2-24b-instruct-2512` | **68.0% SWE-bench**; dense 24B; 256K context; European (Mistral AI 🇫🇷) |

See [docs/MODELS.md](docs/MODELS.md) for benchmark data and [docs/TUNING.md](docs/TUNING.md) for context-window tuning.

## Python dependencies

Declared in `pyproject.toml`; installed automatically by pip or pipx. Dependencies: `lmstudio`, `httpx`, `inquirerpy`, `pyflakes`, `autoflake`. All pure-Python.

### Optional: OpenVINO inference

```sh
pip install openvino openvino-genai
```

Enables `mu serve` and the OpenVINO backend. CPU-only; no GPU or LM Studio required.

### Optional: plan lint (spaCy)

`mu lint` checks `PLAN.md` for entity inconsistencies, vague verbs, and underspecified tasks — no LLM involved. When `MU_LINT_PLAN=1`, warnings feed back to the planner for one revision pass.

```sh
pip3 install 'mu[lint]'
python3 -m spacy download en_core_web_sm
```

## Skills

Prompt fragments injected into the planner for specific domains. Stored in `skills/<name>/SKILL.md`, selected automatically based on the goal.

| Skill | What it enforces |
|-------|-----------------|
| `python-env` | venv isolation, pytest version rules, stateless tests |
| `task-planner` | PLAN.md format — flat checklist, explicit filenames, tab-indented Makefile recipes |

## Package structure

```
src/mu/                Python package
  agent.py             autonomous orchestration loop
  reflexes.py          deterministic post-write fixers
  session.py           writer loop and repair loop
  toolchain.py         toolchain detection and problem catalog filtering
  plan.py              PLAN.md parsing
  client.py            LM Studio / OpenVINO HTTP client
  ov_server.py         OpenVINO GenAI OpenAI-compatible server
  archive.py           session tombstones (~/.mu/sessions/)
  __main__.py          CLI and all commands
models-catalog.json    curated model specs
problems-catalog.json  dojo problem set with toolchain requirements
skills/                skill prompts injected by the planner
dojo/                  stress-test working directories (gitignored)
```

## Dojo

The dojo stress-tests mu against a fixed problem set of ten goals spanning C, Python, Go, Rust, C#, Node, and full-stack TypeScript. Problems are defined in `problems-catalog.json`; only problems whose toolchains are installed are run.

```sh
bash sit.sh            # run all available problems once
bash sit.sh p6-rust    # run one problem
bash practice.sh       # repeated rounds: run, distill failures, reflect, repeat
```

`practice.sh` is the training loop (see the intro): each round runs the full set, tags every failed session with its distilled root cause, and prints a per-problem pass-rate table worst-first so the next reflex to write is obvious.

### Problem status

Outcomes are stochastic (a weak model varies run to run). The block below is the **measured** pass rate from the most recent `practice.sh` run (auto-updated at the end of every round); the curated table beneath it records *why* each problem passes.

<!-- DOJO-RESULTS:START (auto-generated by practice.sh — do not edit by hand) -->
_No measured results yet. Run `bash practice.sh` to populate this._
<!-- DOJO-RESULTS:END -->

| Problem | Goal | Toolchain | Status | Reflex that carries it |
|---|---|---|---|---|
| p1-helloworld | C hello world | clang | ✅ reliable | Makefile tab/target normalizers |
| p2-sqlite | Python SQLite todo + pytest | python3 | ✅ reliable | SQLite test-isolation, stdlib/import fixers |
| p3-sdl2 | Draw a line via SDL2 | clang, sdl2 | ✅ reliable | `sdl2-config` Makefile fixers |
| p4-fibonacci | C# Fibonacci | dotnet | ✅ reliable | C# using/brace/duplicate-class fixers |
| p5-gin | Go HTTP `/ping` (Gin) | go | ✅ reliable | blocking `./binary` test command rewritten to `go test ./...` |
| p6-rust | Rust Fibonacci CLI | cargo | ✅ reliable | `Cargo.toml` bad-dependency guard at the test gate |
| p7-flask | Flask REST + SQLite + pytest | python3 | ✅ reliable | runtime-`NameError` → `from main import app` resolver |
| p8-node-todo | Node todo + jest | node | ✅ reliable | jest config / `npx jest` / package.json fixers |
| p9-vue-todo | Vue 3 + TS todo + vitest | node | ⚠️ stochastic | vitest globals/run-mode, `@vue/test-utils` install |
| p10-dotnet-vue-blog | ASP.NET + Vue full-stack blog | dotnet, node | ❌ hard | architect mode; multi-project ceiling |

✅ passes nearly every round · ⚠️ passes some rounds · ❌ rarely passes

### Top 3 challenges to solve

1. **Degenerate generation.** Weak models fall into repetition loops or emit malformed structured output — a `print(f"{task[print(f"{task[…` loop that corrupts a file from the first token, or a Vue `<template>` with an `Invalid end tag` from a duplicated block (p9). These cannot be reconstructed by a reflex (you can't recover intent from a loop), so they must be *prevented* at the sampler. Partly addressed by a windowed `repeat_penalty` (`MU_REPEAT_PENALTY`); not fully solved.
2. **Full-stack orchestration (p10).** Coordinating a backend, a frontend, and a cross-language test harness (dotnet + vitest) exceeds a small model's planning coherence within the context budget. Architect mode and staged plans help but it remains the hardest problem.
3. **Separating model-ceiling failures from deterministic ones.** A failure that recurs with the *same* root cause every round is a general class to turn into a reflex; one that varies run to run is model quality and must not be overfit. This is why `practice.sh` measures across rounds — the discipline that keeps reflexes general rather than problem-specific.

See [DOJO.md](DOJO.md) and [PRACTICE.md](PRACTICE.md) for detail.
