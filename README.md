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
| `mu reflect` | Distil recent failed sessions into docs/challenges/README.md |
| `mu kb` | Build/show the reflex knowledge base — reflex catalog + per-model profiles |
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

## Model selection

mu picks its model with two env vars: `MU_AGENT_MODEL` (the LM Studio model id to
talk to) and `MU_NUM_CTX` (KV-cache context, default 6000). Pinning `MU_AGENT_MODEL`
matters — without it mu auto-selects the first `/v1/models` entry, which can be a
model too large to load.

`make setup-host` sets both for this machine: it probes the GPU and writes
`~/.zshrc.mu` (machine-local, outside the repo) — the 7B
(`qwen2.5-coder-7b-instruct`) with `MU_NUM_CTX=12288` on a discrete NVIDIA card
with ≥6 GB VRAM, the snappier 3B on everything else. Re-run after a hardware change.

`~/.zshrc.mu` only takes effect if your shell sources it. Add to `~/.zshrc` (or
`~/.bashrc`):

```sh
[ -r "$HOME/.zshrc.mu" ] && source "$HOME/.zshrc.mu"
```

(The selection thresholds mirror those in the [dotfiles](https://github.com/jacobandresen/dotfiles)
`setup-host`, which pins pi's model the same way so mu and pi share one local model.)

## Python dependencies

Declared in `pyproject.toml`; installed automatically by pip or pipx. Dependencies: `lmstudio`, `httpx`, `inquirerpy`, `pyflakes`, `autoflake`. All pure-Python.

## Dojo

The dojo stress-tests mu against a fixed problem set of twelve goals spanning C, Python, Go, Rust, C#, Node, full-stack TypeScript, and SDL2 graphics/physics. Problems are defined in `problems-catalog.json`; only problems whose toolchains are installed are run.

```sh
mu dojo run               # run all available problems once
mu dojo run <problem-id>  # run one problem
mu dojo practice          # repeated rounds: run, distill failures, reflect, repeat
```

`mu dojo practice` is the training loop (see the intro): each round runs the full set, tags every failed session with its distilled root cause, and prints a per-problem pass-rate table worst-first so the next reflex to write is obvious. See [DOJO.md](DOJO.md) for the full command surface.

### Problem status

The measured per-problem result of the most recent `mu dojo practice` round — with a visual
solved marker (✅ / ❌ / ➖) — lives in the problem index:
**[docs/problems/README.md](docs/problems/README.md)** (auto-rewritten each round). Each
problem links to its own page: statement, what it builds, last-run errors and token usage,
and the reflexes that carry it. Recurring failure classes are catalogued in
[docs/challenges/](docs/challenges/README.md).

See [DOJO.md](DOJO.md) for the problem set, the training loop, and the ranked improvement backlog (open problems). See [docs/ablations.md](docs/ablations.md) for the log of behaviour levers tried and their A/B verdicts.
