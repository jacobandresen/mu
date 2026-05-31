# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai).

**Requires:** Python 3.11+, LM Studio running at `localhost:1234`

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
| `mu model load <id>` | Load a model via the LM Studio SDK |
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

## Recommended models

| VRAM | Model | Notes |
|------|-------|-------|
| 8 GB | `qwen/qwen2.5-coder-7b-instruct` | Best 8 GB option; 88.4% HumanEval; native tool calling |
| 16 GB | `mistralai/devstral-small-2507` | 53.6% SWE-bench (#1 open-source); agentic coding |
| 32 GB | `unsloth/qwen3-coder-30b-a3b-instruct` | MoE 30B/3B active; 256K context |

See [docs/MODELS.md](docs/MODELS.md) for benchmark data and [docs/TUNING.md](docs/TUNING.md) for context-window tuning.

## Python dependencies

Declared in `pyproject.toml`; installed automatically by pip or pipx. Dependencies: `lmstudio`, `httpx`, `inquirerpy`, `pyflakes`, `autoflake`. All pure-Python.

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
  client.py            LM Studio HTTP client
  archive.py           session tombstones (~/.mu/sessions/)
  __main__.py          CLI and all commands
models-catalog.json    curated model specs
problems-catalog.json  dojo problem set with toolchain requirements
skills/                skill prompts injected by the planner
dojo/                  stress-test working directories (gitignored)
```

## Dojo

The dojo stress-tests mu against a fixed problem set. Problems are defined in `problems-catalog.json`; only problems whose toolchains are installed are run.

```sh
bash sit.sh            # run all available problems
bash sit.sh p6-rust    # run one problem
```

Current baseline: **7/7** with `qwen2.5-coder-7b-instruct`. See [DOJO.md](DOJO.md) and [PRACTICE.md](PRACTICE.md).
