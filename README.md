# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai).

**Requires:** `nvim`, `fzf`, LM Studio running at `localhost:1234`

## Quick start

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make install

# Start LM Studio, load a model (e.g. Qwen2.5-Coder-7B-Instruct), start the server
mu check                          # verify dependencies
mu agent "write a Flask REST API with SQLite and pytest tests" --dir myproject
```

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop |
| `mu check` | Verify all dependencies are installed |
| `mu clean [dir...]` | Report large files in the given directories (default: `/`) |
| `mu model` | Browse and select LM Studio models |
| `mu setup` | Install system dependencies |
| `mu theme` | Pick and apply a base16 colour scheme |
| `mu extract` | Salvage files from an agent session log |
| `mu version` | Print mu version |

## System dependencies

`mu setup` installs the following packages (via `brew` on macOS, `pacman` on Arch, `apt` on Debian/Ubuntu):

| Tool | Purpose |
|------|---------|
| `neovim` | Editor |
| `make`, `gcc`, `llvm`/`clang` | C/C++ compilation and linting (`clang-tidy`) |
| `node`, `npm` | JavaScript/TypeScript runtime |
| `python` / `python3` | Python runtime |
| `jq` | JSON processing |
| `fzf` | Fuzzy finder (model picker, theme picker) |
| `ripgrep`, `fd` | Fast search tools |
| `SDL2` | Graphics library (for SDL2 practice problem) |
| `ruff` | Python linter |
| `fpc` | Free Pascal compiler |

**LM Studio** is not installed by `mu setup` — download it from [lmstudio.ai](https://lmstudio.ai), load a model, and start the local server. mu connects to `http://localhost:1234` by default (override with `MU_LMSTUDIO_HOST`).

## Recommended models

| VRAM | Model | Notes |
|------|-------|-------|
| 8 GB | `Qwen2.5-Coder-7B-Instruct` Q4_K_M | Best 8 GB option; 88.4% HumanEval; native tool calling |
| 16 GB | `Devstral-Small-2507` Q4_K_M | 53.6% SWE-bench (#1 open-source); agentic coding |
| 32 GB | `Qwen3-Coder-30B-A3B-Instruct` Q4_K_M | MoE 30B/3B active; 256K context |

See [docs/MODELS.md](docs/MODELS.md) for full benchmark research and HuggingFace links.

## Install

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make install
```

## Practice

The `dojo/` directory is where mu is stress-tested by running a guest model through a fixed problem set (P1–P7). See [docs/PRACTICE.md](docs/PRACTICE.md) for the problem set and [docs/RUNS.md](docs/RUNS.md) for results across sessions.

## How it works

mu implements *harness engineering* — designing the scaffolding around an LLM that turns it into a reliable autonomous agent. This covers the orchestration loop, the `sensors/` subsystem (deterministic code fixers), the planning pipeline, and the lint/test verification gates. See [docs/HARNESS_ENGINEERING.md](docs/HARNESS_ENGINEERING.md) for a detailed explanation.
