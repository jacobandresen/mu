# Ollama Tuning Guide — Mac M2 8 GB

Observations collected from dojo sessions running qwen3:8b and gemma4:e2b on a MacBook with M2 (8 GB unified memory).

---

## Hardware context

| Property | Value |
|----------|-------|
| SoC | Apple M2 (unified memory) |
| Total RAM | 8 GB |
| Memory architecture | CPU + GPU share the same pool |
| Ollama version | 0.24.0 |
| Page size | 16 KB (not 4 KB as on x86) |

With only 8 GB shared between OS, GPU, and the model, headroom is tight.
A fully loaded qwen3:8b occupies roughly 6 GB, leaving ~2 GB for the system.

---

## Runtime memory snapshot (qwen3:8b, num\_ctx=8096)

| Segment | Size |
|---------|------|
| Model (wired, GPU layers) | 5.12 GB |
| Model total RSS | 5.99 GB |
| macOS wired pages | 6.16 GB |
| Compressed pages | 3.80 GB → 0.42 GB physical |
| Swap used | 1.52 GB / 2.00 GB |
| Free physical | ~44 MB |

At 8096 context the system is under heavy memory pressure.
The KV cache for qwen3:8b at 8096 tokens is ~600 MB (vs ~300 MB at 4096).
Swap usage of 1.5 GB confirms the OS is compressing pages to stay afloat.

---

## The 5 key parameters

### 1. `num_ctx` — Context window

Set via `MU_NUM_CTX` env var (read by every `/api/chat` call and by `ensureAgentModel`).

| Value | KV cache | Behaviour |
|-------|----------|-----------|
| 2048 | ~150 MB | Very fast; too small for multi-file tasks |
| 4096 | ~300 MB | Default; works for simple tasks, risks truncation on complex ones |
| 6000 | ~450 MB | Good balance — fits most code tasks without swap pressure |
| 8096 | ~600 MB | More context, triggers swap on 8 GB M2, noticeably slower |
| 16384 | ~1.2 GB | Not viable on 8 GB M2 — excessive swap |

**Recommendation:** `MU_NUM_CTX=6000` on M2 8 GB. It gives enough room for multi-file code tasks without pushing the system into heavy swap. Use 8096 only if a problem consistently fails at 6000 (e.g. very long prompts).

**Measured impact:** Doubling ctx from 4096 → 8096 made P1 2.6× slower (64 s → 165 s) and P3 6× slower (155 s → 928 s). The extra swap I/O dominates for long sessions.

**Dojo default is 3072:** `dojo/run.sh` sets `MU_NUM_CTX=3072` unless overridden. This is conservative (fast, low swap) but still not immune to timeouts — see Memory pressure warning below.

---

### 2. `num_thread` — CPU inference threads

Set via `MU_NUM_THREAD` (passed to `/api/chat` options and to `ollama create` params).

On Apple Silicon, ollama uses Metal for matrix multiplication. `num_thread` controls the CPU threads that handle non-GPU work (tokenization, scheduling, attention layers kept on CPU when VRAM runs short).

| Value | Effect on M2 |
|-------|-------------|
| 0 / unset | Auto (ollama picks ~4–8 threads); Metal GPU handles matmuls |
| 1 | Forces everything through one CPU thread — **5–10× slower** |
| 4 | Reasonable balance on M2 (4 performance cores) |
| 8 | Uses efficiency cores too; marginal extra throughput |

**Recommendation:** Leave `MU_NUM_THREAD` unset (default 0) on M2. The GPU handles the heavy work and num_thread=1 is catastrophically slow.

**Measured impact (session A vs previous run):**

| Problem | 4096ctx default-thread | 8096ctx num\_thread=1 | Slowdown |
|---------|----------------------|----------------------|---------|
| P1 helloworld | 64 s | 165 s | 2.6× |
| P2 sqlite | — (timeout) | 327 s ✓ | — |
| P3 SDL2 | 155 s | 928 s | 6× |

P3's 6× slowdown is largely from the repair step timing out under single-thread pressure.

---

### 3. `temperature` — Output randomness

Set in the `qwen3:agent` modelfile via `ollama create`.

| Value | Effect |
|-------|--------|
| 0 | Fully deterministic — always picks the highest-probability token |
| 0.1–0.3 | Very low randomness; useful when 0 gets stuck in repetition |
| 0.7 | Default Ollama value; too creative for code generation |
| 1.0+ | High variance; poor for structured outputs like PLAN.md |

**Recommendation:** `temperature=0` for mu's agentic code tasks. The model needs to produce structured outputs (PLAN.md checklists, syntactically correct code) where creativity is harmful. This is already the default in `ensureAgentModel`.

**Note:** Qwen3 supports inline thinking mode (`/think`, `/no_think` tokens). At temperature=0 with thinking disabled, outputs are fast and consistent.

---

### 4. `OLLAMA_NUM_PARALLEL` — Concurrent inference requests

Set as an environment variable when starting `ollama serve`.

| Value | Effect |
|-------|--------|
| 1 | One request at a time; minimal memory overhead |
| 2 | Two simultaneous requests; needs 2× KV cache — not viable on 8 GB |
| 4+ | Default; fine on machines with >16 GB; OOM risk on 8 GB |

**Recommendation:** `OLLAMA_NUM_PARALLEL=1` on M2 8 GB. mu's agent loop is sequential by design (plan → write → lint → test); there's never concurrent inference within one dojo problem.

Setting this to 1 ensures the model doesn't pre-allocate extra KV cache slots for phantom parallel requests.

---

### 5. Quantization — Model weight precision

The quantization level is baked into the GGUF file and set when creating the `qwen3:agent` model.

| Format | Size | Decode speed | Quality |
|--------|------|-------------|---------|
| Q2_K | ~3.0 GB | Fastest | Noticeably degraded |
| Q4_K_M | ~5.2 GB | Good (15–25 tok/s on M2) | Slightly below fp16 |
| Q6_K | ~6.5 GB | Slower | Near-lossless |
| Q8_0 | ~8.7 GB | Slow | Very close to fp16 |
| fp16 | ~16 GB | Slowest | Exact |

`qwen3:8b` from the Ollama registry ships as **Q4_K_M** — the sweet spot for 8 GB M2:
- Fits with room for system + 6000-context KV cache
- Produces correct, idiomatic code for all tested problems (P1–P7)
- Q8_0 does not fit in 8 GB alongside a 6000+ context

**Recommendation:** Keep Q4_K_M. Don't try Q8_0 on 8 GB — you'll swap constantly.

---

## Model recommendation for M2 8 GB

| Model | Size | Dojo score | Notes |
|-------|------|-----------|-------|
| **qwen3:8b Q4_K_M** | 5.2 GB | 6/7 (v0.3) · 4/7 (v0.5, 2026-05-20)¹ | Best quality that fits |
| **gemma4:e2b** | 7.2 GB | 3/7 baseline (v0.5, 2026-05-21)² | Very fast writes; repair tool-call unreliable |
| qwen2.5-coder:7b Q4_K_M | 4.7 GB | Comparable for pure coding | Less capable at planning |
| qwen3:4b Q4_K_M | 2.5 GB | Not tested standalone | Much faster; likely lower score |

¹ The v0.5.0 4/7 score reflects three deterministic sensor bugs in the agent harness (now fixed), not a model capability regression.

² gemma4:e2b baseline 3/7 improved with new sensors targeting its specific failure patterns (see gemma4 section below).

**Use qwen3:8b for highest score.** The 0.5 GB size difference over qwen2.5-coder:7b buys significantly better planning capability. gemma4:e2b is a viable alternative on 8 GB if sensor coverage is high — its write speed is 3–5× faster but repair tool-call reliability is lower.

---

## Recommended Ollama startup

```sh
OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve
```

## Recommended mu environment

```sh
export MU_AGENT_BASE_MODEL=qwen3:8b
export MU_NUM_CTX=6000          # good balance; raise to 8096 for very long tasks
# MU_NUM_THREAD — leave unset (GPU default)
# temperature=0 — baked into qwen3:agent at creation time
```

---

## Memory pressure warning

At `num_ctx=8096` on 8 GB M2, the system runs with only ~44 MB free physical RAM and 1.5 GB swap active. This manifests as:
- Slower generation (swap I/O latency)
- Occasional kernel page-compression stalls
- Repair sessions hitting timeout (writer timeout = 450 s at 8096 ctx with 1.5× scale)

**Timeouts are not exclusive to large contexts.** Session I (2026-05-21) at `num_ctx=3072` saw Ollama drop two connections during P2's repair loop (220 s and 117 s wall-clock before deadline). The repair prompt was ~1000 prompt tokens + ~1000 generated tokens — a heavier generation than the write phase — and that alone was enough to trigger swap pressure on 8 GB. Lower context reduces *baseline* memory use but does not eliminate timeout risk under sustained generation load.

Dropping to `num_ctx=6000` reclaims ~150 MB of KV cache and meaningfully reduces swap pressure.

---

## Summary table

| Parameter | Safe value for M2 8 GB | Avoid |
|-----------|----------------------|-------|
| `num_ctx` | 6000 | >10000 (OOM) |
| `num_thread` | unset (0) | 1 (5–10× slowdown) |
| `OLLAMA_NUM_PARALLEL` | 1 | >1 (doubles KV cache) |
| `temperature` | 0 | >0.5 (breaks structured output) |
| Quantization | Q4_K_M | Q8_0 (doesn't fit in 8 GB with context) |

---

## gemma4:e2b — Model-specific findings (2026-05-21)

gemma4:e2b is Google's Gemma 4 efficient 2B model at 7.2 GB. Tested on M2 8 GB with `num_ctx=3072`.

### Speed

gemma4:e2b is dramatically faster per token than qwen3:8b at the same context:

| Problem | gemma4:e2b run 1 | gemma4:e2b run 2 | gemma4:e2b run 3 | qwen3:8b (v0.5, 2026-05-20) |
|---------|-----------------|-----------------|-----------------|------------------------------|
| P1 helloworld | 35 s ✓ | 20 s ✓ | 16 s ✓ | 60 s ✓ |
| P2 sqlite | X 424 s | X 223 s | X 810 s | 323 s ✓ |
| P3 sdl2 | X 177 s | 49 s ✓ | X 59 s | X 591 s |
| P4 fibonacci | X 78 s | 21 s ✓ | 19 s ✓ | 189 s ✓ |
| P5 go/gin | 16 s ✓ | 14 s ✓ | 14 s ✓ | X 401 s |
| P6 rust | 23 s ✓ | 17 s ✓ | 16 s ✓ | 135 s ✓ |
| P7 flask | X 325 s | X 173 s | X 324 s | X 780 s |

Run 1: **3/7**, Run 2: **5/7** (P3 SDL2 + P4 Fibonacci fixed by new sensors), Run 3: **4/7** (regression: P3 new SDL3 API bug).

**Run 3 regression (P3):** Model wrote `SDL_DestroySurface` (SDL3 API) instead of `SDL_FreeSurface` (SDL2). A new sensor variant appeared in the model's output. Fix: `FixSDLDestroySurface` sensor added.

**Run 3 P7 failure:** Makefile had space-indented recipe lines; `FixNoTargets` was a no-op because a target line existed, and space-indented lines caused `missing separator`. Fix: `FixMakefileSpaceIndent` sensor added (runs first in chain).

**Run 3 P2 failure:** Model wrote ~1200 tokens of prose for `test_todo.py` without calling Write, then 3 server drops consumed 800 s of budget. Fix: code-block extraction in `session.go` — when model generates prose with a fenced code block instead of calling Write, extract and write the file directly.

Write phase typically completes in 3–60 s per file. Simple files (go.mod, Cargo.toml) resolve in 2–6 s.

### Tool-call reliability in write vs repair phase

gemma4:e2b calls tools reliably in the **write phase** for simple and medium-complexity files.
It consistently fails to call tools in the **repair phase**:

- **Write phase**: tool call success rate ~85% (some files need near-empty retry)
- **Repair phase**: tool call success rate ~0% — model generates long explanations (600–1200 tokens) then emits gen=1 tokens and stops without calling Edit or Write

**Root cause:** The repair prompt ("Tests are failing. Fix the broken code now.") is conversational; gemma4:e2b treats it as a discussion rather than a directive action. The write prompt ("You ONLY have the Write tool. Use it immediately. Stop immediately after.") is directive and works.

**Fix applied:** Repair prompt rewritten with numbered imperative rules: "Call Edit or Write RIGHT NOW. Do not explain."

### Code generation quirks

| Issue | Frequency | Fix |
|-------|-----------|-----|
| Markdown in XML (##PropertyGroup>) | 1/7 per run | `FixCsprojMarkdownCorruption` sensor |
| SQLite init only in `__main__` | 1/7 per run | `FixSQLiteInitDb` sensor |
| Makefile defines SDL_CFLAGS but doesn't use it | 1/7 per run | `FixMakefileSDL2` sensor |
| Makefile missing pip install before pytest | 1/7 per run | `FixMakefilePipInstall` sensor |
| Makefile recipe uses spaces instead of tabs | 1/7 per run | `FixMakefileSpaceIndent` sensor |
| Makefile orphan commands outside any target | 1/7 per run | `FixOrphanTopLevelCommands` sensor |
| SDL3 API (SDL_DestroySurface) in SDL2 code | 1/7 per run | `FixSDLDestroySurface` sensor |
| Code written as prose (no Write tool call) | 1/7 per run | Code-block extraction in session.Run |
| Near-empty file (stub < 100 bytes) | ~1–2/7 per run | Existing near-empty retry |

### Memory (gemma4:e2b at 7.2 GB on M2 8 GB)

The model at 7.2 GB leaves only ~0.8 GB for system + KV cache at `num_ctx=3072` (~230 MB KV).
The system runs but under light swap pressure. Generation is still fast because the model weights
are largely resident in GPU memory; only the KV cache and OS compete for the remaining headroom.

**Recommendation:** `MU_NUM_CTX=3072` for gemma4:e2b on 8 GB M2. Do not exceed 4096 — the KV
cache at 4096 (~300 MB) plus the 7.2 GB model leaves the system critically short of free RAM.
