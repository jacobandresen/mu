# Model Research: Dojo Benchmark Candidates

Last updated: 2026-05-23

## What the dojo requires

Seven problems across Python, C (SDL2), C# (dotnet), Go (Gin), Rust (cargo), and a hard Flask+SQLite+pytest problem.
The top failure modes (from DOJO.md) are:

1. **Tool calling failure** — model generates prose instead of calling Write; repair agent never acts.
2. **API hallucination** — wrong library versions (gin v2.0.0), SDL3 vs SDL2 APIs, bad go.mod pins.
3. **Makefile syntax** — spaces instead of tabs, orphan commands, wrong SDL2 wiring.
4. **Multi-language breadth** — model must write idiomatic Python, C, Go, Rust, C# in one session.

Tool calling reliability is the single biggest lever: gemma4:e2b hit 5/7 with sensors but collapsed
on P2/P7 every time because the repair agent generated explanations instead of tool calls.

The most predictive benchmark for the dojo is **SWE-bench Verified** (fixing real GitHub issues with
tools) — not HumanEval (Python autocomplete). Models that score well on SWE-bench have demonstrated
they can call tools, iterate on failures, and write correct multi-file code.

---

## Benchmark glossary

| Benchmark | What it tests | Why it matters for dojo |
|---|---|---|
| **HumanEval** | Python function completion from docstrings | Proxy for code fluency; doesn't test tool use or multi-lang |
| **MBPP** | 374 basic Python programming problems | Similar to HumanEval; easy for modern models |
| **MultiPL-E** | HumanEval translated to 18 languages | Tests multi-language breadth — directly relevant to dojo |
| **SWE-bench Verified** | 500 real GitHub issues; model must submit a passing patch | Best proxy for dojo: tool use + debugging + multi-file |
| **BFCL** | Berkeley Function Calling Leaderboard; structured tool call accuracy | Directly tests whether the model calls tools correctly |

---

## Tiered recommendations by VRAM

### Tier 1 — 8 GB VRAM (fits current hardware)

**Winner: `Qwen2.5-Coder-7B-Instruct` Q4_K_M (~4.5 GB)**

| Benchmark | Score |
|---|---|
| HumanEval | 88.4% |
| MultiPL-E | Strong across Python, C, Go, Rust, Java |
| Tool calling | Native support; LM Studio tool-use docs use this as example |

HuggingFace:
- [`bartowski/Qwen2.5-Coder-7B-Instruct-GGUF`](https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF) (recommended)
- [`Qwen/Qwen2.5-Coder-7B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF) (official)
- [`lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF`](https://huggingface.co/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF)

Why it wins at this tier: trained on 5.5T code tokens; outperforms general models twice its size on
code tasks; strong tool calling; 128K context; 92+ languages including all dojo targets.

**Runner-up: `DeepSeek-R1-Distill-Qwen3-8B` Q4_K_M (~5 GB)**

R1 reasoning distilled into an 8B base (Qwen3). Better on complex reasoning / multi-step debugging
but slower. Useful if the repair phase is the bottleneck.

HuggingFace: search `DeepSeek-R1 8B GGUF bartowski`

---

### Tier 2 — 16 GB VRAM

**Winner: `Devstral-Small-2507` Q4_K_M (~14.3 GB)**

| Benchmark | Score |
|---|---|
| SWE-bench Verified | **53.6%** — #1 open-source model at time of release |
| Tool calling | Purpose-built for agentic code editing (OpenHands scaffold) |
| Context | 128K tokens |

HuggingFace:
- [`mistralai/Devstral-Small-2507_gguf`](https://huggingface.co/mistralai/Devstral-Small-2507_gguf) (official)
- [`bartowski/mistralai_Devstral-Small-2507-GGUF`](https://huggingface.co/bartowski/mistralai_Devstral-Small-2507-GGUF)
- [`unsloth/Devstral-Small-2507-GGUF`](https://huggingface.co/unsloth/Devstral-Small-2507-GGUF)

This is the most compelling upgrade from Qwen2.5-Coder-7B. Devstral is fine-tuned from
Mistral-Small-3.1 specifically for agentic software engineering — it's trained to call tools,
iterate on test failures, and write patches across multiple files. The 53.6% SWE-bench score
means it solves roughly half of real GitHub bug reports autonomously; that's exactly the dojo
repair-loop problem. 24B parameters, ~14.3 GB Q4_K_M.

**Runner-up: `DeepSeek-Coder-V2-Lite-Instruct` Q4_K_M (~10 GB)**

MoE architecture: 16B total params, only 2.4B active per forward pass — fast inference.
128K context, 338 programming languages. Strong on code but less agentic than Devstral.

HuggingFace:
- [`bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF`](https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF)
- [`lmstudio-community/DeepSeek-Coder-V2-Lite-Instruct-GGUF`](https://huggingface.co/lmstudio-community/DeepSeek-Coder-V2-Lite-Instruct-GGUF)

---

### Tier 3 — 32 GB VRAM

**`Qwen3-Coder-30B-A3B-Instruct` Q4_K_M (~18 GB)**

MoE: 30B total, ~3B active. Purpose-built coding agent model from Qwen team; 256K context;
strong agentic tool use per benchmark. Comparable compute cost to a 3B dense model but retains
30B knowledge.

HuggingFace: [`unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`](https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF)

---

## vs. models currently on the LM Studio server

| Model | Dojo problem | Notes |
|---|---|---|
| `google/gemma-4-e2b` | Repair agent never calls tools (CHALLENGES #1, #9) | Fast but unreliable; fails P2/P7 every run |
| `mistralai/mistral-7b-instruct-v0.3` | General model, pre-2025, no code specialization | Likely worse than Qwen2.5-Coder on multi-lang code |
| `Qwen2.5-Coder-7B-Instruct` | Best 8GB option | **Recommended for 8GB** |
| `Devstral-Small-2507` | Agentic, SWE-bench #1 open-source | **Recommended for 16GB** |

---

## vs. Qwen3-8B (tested at 1/7 in honest harness)

Qwen3-8B is a general model. Its 1/7 score reflects the absence of plan-gen and sensors.
Qwen2.5-Coder-7B is purpose-built for code and should meaningfully outperform it on tool-call-heavy
tasks — especially the repair loop. Qwen3-8B scores 72% HumanEval vs. 88.4% for Qwen2.5-Coder-7B.

---

## Why NOT these models

| Model | Why not |
|---|---|
| `Codestral-22B` | Pre-2025 completion model; no agentic training; 22B needs 16GB; Devstral is better for same VRAM |
| `MiniMax-M2.5` | 230B params; 51 GB even at 1-bit quant; not feasible locally |
| `Qwen3-Coder-Next` | 80B MoE; too large for any consumer GPU |

---

## Integration

mu connects to **LM Studio at `localhost:1234`** via its OpenAI-compatible API (`src/mu/client.py`).
Override the host with `MU_LMSTUDIO_HOST`.

To use a model with mu:

1. Load it in LM Studio (Models tab → load)
2. Start the local server (LM Studio → Developer → Start Server)
3. Run:
   ```
   mu agent --model <model-id> "your goal"
   ```
   Or set the env var permanently:
   ```
   export MU_AGENT_MODEL=qwen/qwen2.5-coder-7b-instruct
   ```

If `--model` and `MU_AGENT_MODEL` are both unset, mu uses the first model loaded in LM Studio.

---

## Sources

- [Best LLM for Coding 2026: Real Benchmarks](https://whatllm.org/best-llm-for-coding)
- [Best Local LLMs for 8GB VRAM (2026)](https://lmsa.app/blog/the-best-local-llm-models-for-coding-with-an-8gb-vram-gpu-2026/)
- [Best Local Coding Models Ranked: Every VRAM Tier](https://insiderllm.com/guides/best-local-coding-models-2026/)
- [Qwen3 vs Qwen2.5-Coder comparison](https://docs.bswen.com/blog/2026-03-27-qwen3-vs-qwen25-coder-programming/)
- [Best Coding LLMs 2026: Qwen vs DeepSeek vs Llama](https://www.promptquorum.com/local-llms/best-local-llms-for-coding)
- [Codestral guide and benchmark context](https://ucstrategies.com/news/codestral-guide-specs-benchmarks-local-deployment-2026/)
- [Devstral run & fine-tune guide (Unsloth)](https://unsloth.ai/docs/models/tutorials/devstral-how-to-run-and-fine-tune)
- [Qwen3-Coder GitHub](https://github.com/QwenLM/Qwen3-Coder)
- [SWE-bench Verified leaderboard](https://www.swebench.com/verified.html)
- [BFCL Function Calling Leaderboard](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/)
- [bartowski/Qwen2.5-Coder-7B-Instruct-GGUF](https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF)
- [bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF](https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF)
- [mistralai/Devstral-Small-2507_gguf](https://huggingface.co/mistralai/Devstral-Small-2507_gguf)
- [unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF](https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF)
