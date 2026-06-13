# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal using a local LLM via [LM Studio](https://lmstudio.ai).

**mu is an agent harness that employs *reflexes* — deterministic, condition→action fixers — to repair the mistakes weaker local models make.** A small model (e.g. a 3B) writes plausible but broken code: an invalid `Cargo.toml` dependency, a test that forgets to import `app`, a Makefile recipe without a tab, a Go test command that blocks forever. Each reflex corrects one *general class* of such error before the lint/test gate runs, so a weak model lands working code far more often than its raw output would allow.

**The reflexes are trained in the `mu dojo practice` loop by stronger models.** `mu dojo practice` runs the dojo repeatedly with a weak model, distills the root cause of every failure, and surfaces the chronic ones; a stronger model (the developer, or an LLM agent like Claude) then reads those failures and encodes a new general reflex or normalizer. Over rounds, the harness accumulates the fixes a weak model can't make for itself. Reflexes must fix a *general* class — never a specific dojo problem.

**Requires:** Python 3.11+ and **LM Studio** running at `localhost:1234`.

## Quick start

```sh
git clone https://github.com/jacobandresen/mu
cd mu
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
source .venv/bin/activate

# Start LM Studio's server and load a model with the lms CLI
lms server start                  # serve on http://localhost:1234
lms load ibm/granite-4.1-3b       # load a model

mu check                          # verify dependencies + toolchains + LM Studio reachable
mu setup                          # install missing toolchains (interactive)
mu agent "write a Flask REST API with SQLite and pytest tests" --dir myproject
```

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop (the main entry point) |
| `mu plan "goal"` | Generate PLAN.md only (no code writing) |
| `mu improve-plan` | Tighten an ambiguous PLAN.md — deterministic spec reflexes plus plan lint |
| `mu architect "goal"` | Generate ARCHITECTURE.md and staged plan files for hard multi-layer problems |
| `mu iterate` | Continue executing an existing PLAN.md |
| `mu model` / `mu model load <id>` | Browse / load LM Studio models |
| `mu check` | Verify dependencies and that LM Studio is reachable |
| `mu setup` | Interactively install missing toolchains |
| `mu reflect` | Distil recent failed sessions into docs/challenges/lessons.md |
| `mu token-report` | Summarise token usage across sessions into token_usage.md |
| `mu kb` | Build/show the reflex knowledge base — reflex catalog + per-model profiles |
| `mu theme` | Pick and apply a base16 colour scheme |
| `mu version` | Print mu version |

## Toolchains

`mu check` shows which compiler toolchains are installed and whether LM Studio is reachable. `mu setup` presents a checklist of missing toolchains and installs only what you select — it never upgrades tools that are already present.

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

## Python dependencies

Declared in `pyproject.toml`; installed automatically by pip or pipx. Dependencies: `lmstudio`, `httpx`, `inquirerpy`, `pyflakes`, `autoflake`. All pure-Python.

## Dojo

The dojo stress-tests mu against a fixed problem set of ten goals spanning C, Python, Go, Rust, C#, Node, and full-stack TypeScript. Problems are defined in `problems-catalog.json`; only problems whose toolchains are installed are run.

```sh
mu dojo run               # run all available problems once
mu dojo run <problem-id>  # run one problem
mu dojo practice          # repeated rounds: run, distill failures, reflect, repeat
```

`mu dojo practice` is the training loop (see the intro): each round runs the full set, tags every failed session with its distilled root cause, and prints a per-problem pass-rate table worst-first so the next reflex to write is obvious. See [DOJO.md](DOJO.md) for the full command surface.

### Problem status

Outcomes are stochastic (a weak model varies run to run). The table below shows the **measured** result of the most recent `mu dojo practice` round (auto-updated at the end of every round). Each problem links to its page in [`docs/problems/`](docs/problems/) — problem statement, what it builds, dominant errors and token usage from the last run, and the reflexes that carry it. Recurring failure classes are catalogued in [challenges](docs/challenges/README.md), each with a detail page under [`docs/challenges/`](docs/challenges/).

<!-- DOJO-RESULTS:START (auto-generated by mu.dojo — do not edit by hand) -->
_Last round: 2026-06-13T10:32:06+02:00 · model: lmstudio-community/qwen2.5-coder-7b-instruct_

| Problem | Solved in last round |
|---|---|
| [p1-helloworld](docs/problems/p1-helloworld.md) | PASS |
| [p2-sqlite](docs/problems/p2-sqlite.md) | STALLED |
| [p3-sdl2](docs/problems/p3-sdl2.md) | PASS |
| [p4-fibonacci](docs/problems/p4-fibonacci.md) | PASS |
| [p5-gin](docs/problems/p5-gin.md) | PASS |
| [p6-rust](docs/problems/p6-rust.md) | PASS |
| [p7-flask](docs/problems/p7-flask.md) | PASS |
| [p8-node-todo](docs/problems/p8-node-todo.md) | STALLED |
| [p9-vue-todo](docs/problems/p9-vue-todo.md) | PASS |
| [p10-dotnet-vue-blog](docs/problems/p10-dotnet-vue-blog.md) | STALLED |
<!-- DOJO-RESULTS:END -->

See [DOJO.md](DOJO.md) for the problem set, the training loop, and open problems. See [TODO.md](TODO.md) for the ranked improvement backlog.
