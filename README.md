# mu

Local AI coding toolkit. Drives an autonomous coding loop from a plain-English goal.

**Requires:** `nvim`, `ollama`, `fzf`, [`pi`](https://www.npmjs.com/package/@earendil-works/pi-coding-agent)

## Commands

| Command | Description |
|---|---|
| `mu agent "goal"` | Autonomous goal-to-code loop |
| `mu check` | Verify all dependencies are installed |
| `mu clean` | Report large files in the current tree |
| `mu model` | Manage the ollama model |
| `mu optimize` | Tune ollama for the agent workload |
| `mu prime` | Pull all curated models |
| `mu run` | Launch pi in offline mode |
| `mu setup` | Install system dependencies |
| `mu theme` | Pick and apply a base16 colour scheme |
| `mu extract` | Salvage files from an agent session log |

## Install

```sh
git clone https://github.com/jacobandresen/mu
cd mu
make install
```

## Practice

See [PRACTICE.md](PRACTICE.md) for a set of problems to run and improve the agent against.

---

By Jacob Andresen — [searchzen.org](https://searchzen.org)
