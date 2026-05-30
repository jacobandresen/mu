# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai).

**Requires:** Python 3.11+, LM Studio running at `localhost:1234`

## Quick start

```sh
# Install mu in an isolated venv (recommended)
python3 -m venv ~/.mu-venv
~/.mu-venv/bin/pip install mu
# Or: pipx install mu   (pipx manages the venv for you)

# From source
git clone https://github.com/jacobandresen/mu
cd mu
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
source .venv/bin/activate

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
| `mu lint [PLAN.md]` | Report deterministic plan warnings (no LLM) |
| `mu version` | Print mu version |

## System dependencies

`mu setup` installs the compiler toolchains the agent needs to build and test the code it generates (via `brew` on macOS, `pacman` on Arch, `apt` on Debian/Ubuntu). mu's own Python dependencies are declared in `pyproject.toml` and installed inside the mu venv — nothing is written to the system Python.

### Compiler toolchains (installed by `mu setup`)

| Tool | Language | macOS | Linux (apt) |
|------|----------|-------|-------------|
| `clang` | C / C++ | `brew install llvm` | `apt install clang clang-tidy` |
| `go` | Go | `brew install go` | `apt install golang` |
| `cargo` / `rustc` | Rust | `brew install rustup && rustup toolchain install stable` | `apt install cargo` |
| `dotnet` | C# | `brew install dotnet` | `apt install dotnet-sdk-8.0` |
| `python3` | Python 3 | pre-installed on macOS 12+ | `apt install python3` |
| `node` / `npm` | JavaScript / TypeScript | `brew install node` | `apt install nodejs npm` |
| `make` | Build system | `brew install make` | `apt install build-essential` |
| `sdl2-config` | SDL2 graphics | `brew install SDL2` | `apt install libsdl2-dev` |

Run `mu check` to verify which tools are installed before running the agent.

**LM Studio** is not installed by `mu setup` — download it from [lmstudio.ai](https://lmstudio.ai), load a model, and start the local server. mu connects to `http://localhost:1234` by default (override with `MU_LMSTUDIO_HOST`).

## Python dependencies

Declared in `pyproject.toml`; installed automatically by pip or pipx. Dependencies: `lmstudio`, `httpx`, `inquirerpy`, `pyflakes`, `autoflake`. All pure-Python.

### Optional: plan lint (spaCy)

`mu lint` runs deterministic checks over `PLAN.md` (entity consistency, vague verbs, underspecified tasks) with no LLM. When `MU_LINT_PLAN=1`, warnings are fed back to the planner for one revision pass.

```sh
pip3 install 'mu[lint]'
python3 -m spacy download en_core_web_sm
```

## Recommended models

| VRAM | Model | Notes |
|------|-------|-------|
| 8 GB | `qwen/qwen2.5-coder-7b-instruct` | Best 8 GB option; 88.4% HumanEval; native tool calling |
| 16 GB | `mistralai/devstral-small-2507` | 53.6% SWE-bench (#1 open-source); agentic coding |
| 32 GB | `unsloth/qwen3-coder-30b-a3b-instruct` | MoE 30B/3B active; 256K context |

See [docs/MODELS.md](docs/MODELS.md) for full benchmark research and HuggingFace links.

### models-catalog.json

`models-catalog.json` is a curated list of models mu knows about. The `mu model` picker reads it to show descriptions and context-window sizes alongside the models currently loaded in LM Studio.

```json
{
  "models": [
    {
      "id": "qwen/qwen2.5-coder-7b-instruct",
      "contextWindow": 32768,
      "input": ["text"],
      "description": "Best 8 GB option. Code specialist, 88.4% HumanEval, native tool calling, 92+ languages."
    }
  ]
}
```

Each entry has `id` (matches the LM Studio model identifier), `contextWindow`, `input` modalities (`text`, `image`), and a short `description`. Models not in the catalog still work — they just show without metadata.

## Skills

Skills are prompt fragments injected into the planner's context to guide the model on specific domains. They live in `skills/<name>/SKILL.md` and are loaded automatically when the planner detects a relevant task.

| Skill | Trigger | What it enforces |
|-------|---------|-----------------|
| `python-env` | Any Python task that installs packages or runs pytest | Isolated venvs, `pytest >= 8` on Python 3.12+, compatible dependency pinning, stateless tests |
| `task-planner` | Goal decomposition at session start | PLAN.md format — flat checklist, explicit filenames, tab-indented Makefile recipes, no runtime-generated files |

To add a skill, create `skills/<name>/SKILL.md` with a YAML frontmatter block (`name`, `description`) followed by the prompt body. The planner selects skills by matching the `description` against the current goal.

## Install

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make deps     # install Python dependencies
make install  # install the `mu` command
```

Or install as an editable Python package:

```sh
pip3 install --break-system-packages -e .
```

## Package structure

```
src/mu/                Python package
  __init__.py          __version__
  __main__.py          CLI (argparse) and all commands
  agent.py             autonomous orchestration loop
  archive.py           session tombstones (~/.mu/sessions/)
  client.py            LM Studio HTTP client
  plan.py              PLAN.md parsing and manipulation
  reflexes.py          deterministic post-write fixers
  session.py           writer loop and repair loop
  tools.py             tool definitions (Write/Edit/Read)
models-catalog.json    curated model specs (read by mu model picker)
skills/                skill prompts injected into the planner
  python-env/          Python venv + pytest rules
  task-planner/        PLAN.md structure rules
dojo/                  stress-test harness (gitignored)
```

## Practice

The `dojo/` directory stress-tests mu by driving a guest model through a fixed problem set (P1–P7) and recording exactly where the autonomous loop breaks. See [PRACTICE.md](PRACTICE.md) for the problem set and [DOJO.md](DOJO.md) for the latest runs and open challenges.

### Using the dojo to refine skills and models

**Skills** — if a class of problems fails because the model consistently makes a category-level mistake (wrong venv setup, bad Makefile structure, stale dependency pins), write or tighten the matching skill in `skills/<name>/SKILL.md`. Re-run the dojo on the affected problems only, compare before/after scores, and record the result in DOJO.md. A skill fix should flip at least one problem from fail → pass without regressing others.

**Models (tensors)** — swap the guest model via `mu model load <id>` or by setting `MU_MODEL` before running the dojo. The DOJO.md run table tracks score per model so regressions are visible. Use `MU_NUM_CTX` to control context window size; larger context lets the repair loop accumulate more history but increases VRAM pressure. See [MODELS.md](docs/MODELS.md) for benchmark data and [TUNING.md](docs/TUNING.md) for the recommended knobs.

The honest-harness rule applies to both: a sensor or skill that pattern-matches a specific problem is invalid — fixes must generalise beyond P1–P7. Record every run in DOJO.md so the score history stays auditable.

## How it works

mu implements *harness engineering* — designing the scaffolding around an LLM that turns it into a reliable autonomous agent. This covers the orchestration loop, the `sensors` module (deterministic code fixers), the planning pipeline, and the lint/test verification gates.
