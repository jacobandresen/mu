# Runs

Timing in seconds per problem. **X** = failed. Linked runs have a `dojo/` directory with logs.

---

## Go era (v0.3–v0.6, Ollama backend) — historical summary

| Run | Score | Notes |
|-----|-------|-------|
| 2026-05-17 (v0.3, qwen3:8b) | **6/7** | Best ever. pi's iterative repair loop. |
| 2026-05-18–22 (v0.4–v0.5, qwen3:8b / gemma4:e2b) | 2–5/7 | Sensor tuning era; peak 5/7 with gemma4:e2b. |
| 2026-05-22 (v0.6, qwen3:8b, honest harness) | **1/7** | Baseline after removing problem-specific sensors and Go plan-gen. |
| 2026-05-23 (v0.6.1, qwen3:8b, honest + repair loop) | **2/7** | Repair loop added back. |

The honest harness deliberately removed all problem-specific sensors and the hardcoded Go
plan-generator to measure the agent's real capability, not the harness author's knowledge of
the test problems.

---

## Python era (v0.7+, LM Studio backend)

| Run | Score | P1 helloworld | P2 sqlite | P3 sdl2 | P4 fibonacci | P5 go/gin | P6 rust | P7 flask |
|-----|-------|--------------|-----------|---------|--------------|-----------|---------|----------|
| [2026-05-23](../dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-23/) (v0.7.0, qwen2.5-coder-7b, LM Studio) | **1/4** | ✓ | X timeout | X timeout | X timeout | — | — | — |

P2/P3/P4 failed due to connection timeouts to remote LM Studio host (`192.168.0.162:1234`); P5–P7
not reached. Score reflects a network-interrupted partial run, not a true baseline. A full local
run is needed to establish the v0.7.0 baseline.
