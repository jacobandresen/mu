# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai).

**Requires:** Python 3.11+, `nvim`, `fzf`, LM Studio running at `localhost:1234`

## Quick start

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make deps     # pip install lmstudio httpx
make install  # symlink bin/mu to ~/.local/bin/mu

# Start LM Studio, load a model (e.g. qwen/qwen2.5-coder-7b-instruct), start the server
mu check                          # verify dependencies
mu agent "write a Flask REST API with SQLite and pytest tests" --dir myproject
```

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop |
| `mu check` | Verify all dependencies are installed |
| `mu clean` | Report large files |
| `mu model` | Browse and select LM Studio models |
| `mu model load <id>` | Load a model via the LM Studio SDK |
| `mu setup` | Install system dependencies |
| `mu extract <log>` | Salvage files from an agent session log |
| `mu version` | Print mu version |

## System dependencies

`mu setup` installs the following packages (via `brew` on macOS, `pacman` on Arch, `apt` on Debian/Ubuntu):

| Tool | Purpose |
|------|---------|
| `neovim` | Editor |
| `make`, `gcc`, `llvm`/`clang` | C/C++ compilation and linting (`clang-tidy`) |
| `node`, `npm` | JavaScript/TypeScript runtime |
| `python3` | Python runtime |
| `jq` | JSON processing |
| `fzf` | Fuzzy finder (model picker) |
| `ripgrep`, `fd` | Fast search tools |
| `SDL2` | Graphics library |
| `ruff` | Python linter |
| `fpc` | Free Pascal compiler |

**LM Studio** is not installed by `mu setup` — download it from [lmstudio.ai](https://lmstudio.ai), load a model, and start the local server. mu connects to `http://localhost:1234` by default (override with `MU_LMSTUDIO_HOST`).

## Python dependencies

```sh
pip3 install lmstudio httpx          # or: make deps
```

mu uses the [LM Studio Python SDK](https://lmstudio.ai/docs/sdk) for model management (listing and loading models) and `httpx` for the OpenAI-compatible chat API.

## Recommended models

| VRAM | Model | Notes |
|------|-------|-------|
| 8 GB | `qwen/qwen2.5-coder-7b-instruct` | Best 8 GB option; 88.4% HumanEval; native tool calling |
| 16 GB | `mistralai/devstral-small-2507` | 53.6% SWE-bench (#1 open-source); agentic coding |
| 32 GB | `unsloth/qwen3-coder-30b-a3b-instruct` | MoE 30B/3B active; 256K context |

See [docs/MODELS.md](docs/MODELS.md) for full benchmark research and HuggingFace links.

## Install

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make deps     # install Python dependencies
make install  # symlink bin/mu into PATH
```

Or install as an editable Python package:

```sh
pip3 install --break-system-packages -e .
```

## Package structure

```
src/mu/           Python package
  __init__.py     version
  __main__.py     CLI (argparse) + all commands
  agent.py        autonomous orchestration loop
  archive.py      session tombstones (~/.mu/sessions/)
  client.py       LM Studio HTTP client
  plan.py         PLAN.md parsing and manipulation
  sensors.py      deterministic code fixers
  session.py      writer loop and repair loop
  tools.py        tool definitions (Write/Edit/Bash/Read)
bin/mu            executable entry point
skills/           skill prompts loaded by the planner
dojo/             stress-test harness
```

## Practice

The `dojo/` directory is where mu is stress-tested by running a guest model through a fixed problem set (P1–P7). See [docs/PRACTICE.md](docs/PRACTICE.md) for the problem set and [docs/RUNS.md](docs/RUNS.md) for results across sessions.

## How it works

mu implements *harness engineering* — designing the scaffolding around an LLM that turns it into a reliable autonomous agent. This covers the orchestration loop, the `sensors` module (deterministic code fixers), the planning pipeline, and the lint/test verification gates. See [docs/HARNESS_ENGINEERING.md](docs/HARNESS_ENGINEERING.md) for a detailed explanation.
