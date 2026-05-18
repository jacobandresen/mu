# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal.

**Requires:** `nvim`, `ollama`, `fzf`, [`pi`](https://www.npmjs.com/package/@earendil-works/pi-coding-agent)

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop |
| `mu check` | Verify all dependencies are installed |
| `mu clean [dir...]` | Report large files in the given directories (default: `/`) |
| `mu model` | Manage the ollama model |
| `mu optimize` | Tune ollama for the agent workload |
| `mu prime` | Pull all curated models |
| `mu run` | Launch pi in offline mode |
| `mu setup` | Install system dependencies |
| `mu theme` | Pick and apply a base16 colour scheme |
| `mu extract` | Salvage files from an agent session log |
| `mu version` | Print mu version |

## System dependencies

`mu setup` installs the following packages (via `brew` on macOS, `pacman` on Arch, `apt` on Debian/Ubuntu):

| Tool | Purpose |
|------|---------|
| `neovim` | Editor used by pi sessions |
| `make`, `gcc`, `llvm`/`clang` | C/C++ compilation and linting (`clang-tidy`) |
| `node`, `npm` | Required by pi |
| `python` / `python3` | Python runtime |
| `jq` | JSON processing |
| `fzf` | Fuzzy finder (model picker, theme picker) |
| `ripgrep`, `fd` | Fast search tools |
| `ollama` | Local LLM runtime |
| `SDL2` | Graphics library (for SDL2 practice problem) |
| `ruff` | Python linter |
| `fpc` | Free Pascal compiler |
| `pi` (npm) | AI coding agent (core runtime) |

## Install

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make install
```

## Practice

The `dojo/` directory is where mu is stress-tested by running a guest model (e.g. `qwen3:8b`) through a fixed problem set (P1–P7). When a problem fails, the failure pattern drives an improvement to a skill file, a sensor, or a plan rule. [PRACTICE.md](PRACTICE.md) describes the problem set. [RUNS.md](RUNS.md) tracks results across sessions.
