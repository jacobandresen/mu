# Quantization, the local-LLM stack, and why model size decides what runs on 8 GB

A field report written from a concrete experiment: finding the best local model for
mu's ten dojo coding problems on an **8 GB M2 MacBook**. The numbers and failure modes
below are all measured on that host (2026-06-20/22), not theoretical.

**Note (2026-06-30):** `scripts/sit.py` now defaults to `mistralai/Mistral-7B-Instruct-v0.2`
(Q4_K_M, ~4.1 GB resident) which follows the same ~4.1 GB ceiling principle described below.

---

## 0. The result that motivated the report

We boarded six models on all ten problems (L0, N=5 each, ranked by problems solved):

| Rank | Model | Quant | File size | Resident | Observed solved /10 |
|---|---|---|---|---|---|
| 1 | **qwen2.5-coder-7b** | **Q3_K_L** | 3.8 GB | 4.09 GB | **7.0** |
| 2= | qwen3-8b | Q3_K_S | 3.77 GB | ~3.8 GB | 5.6 |
| 2= | seed-coder-8b | Q3_K_S | 3.5 GB | 3.80 GB | 5.6 |
| 4 | granite-3.3-8b | Q3_K_S | 3.59 GB | ~3.6 GB | 2.2 |
| 5 | qwen2.5-coder-3b | Q4_K_M | 2.1 GB | ~2.1 GB | 0.8 |
| — | qwen3-8b | **Q3_K_L** | 4.4 GB | ~4.1 GB | **could not run** |
| — | granite-3.3-8b | **Q3_K_L** | 4.4 GB | ~4.1 GB | **could not run** |

The last two rows are the crux: the **same models** that scored 5.6 and 2.2 at Q3_K_S
**could not run at all** one quant step up (Q3_K_L). Understanding why is the point of
this report — and it turns entirely on quantization and where it lands in the stack.

---

## 1. What quantization is

A model's "weights" are the billions of learned numbers that define it. Trained in
**16-bit floating point** (FP16/BF16), an 8-billion-parameter model is `8e9 × 2 bytes ≈
16 GB`. That doesn't fit in 8 GB of RAM, let alone alongside anything else.

**Quantization compresses each weight to fewer bits** — typically 2–8 — trading a little
accuracy for a large drop in size. It is lossy compression for neural nets: instead of
storing every weight at full precision, you store a lower-precision approximation plus a
small amount of per-block scaling metadata so the values can be reconstructed at runtime.

### The K-quant family (what the `Q3_K_L` names mean)

`llama.cpp`'s GGUF format uses **"K-quants"** — the scheme behind almost every local model
today. The name encodes three things:

- **`Q<n>`** — the nominal bits per weight: `Q2` ≈ 2.6, `Q3` ≈ 3.4, `Q4` ≈ 4.5, `Q8` ≈ 8.5
  (effective averages, because metadata adds overhead).
- **`_K`** — "K-quant": weights are grouped into **super-blocks** (256 weights) with
  hierarchical scales, so precision is spent where it matters. Much better quality per bit
  than the old "round everything the same" quants.
- **`_S` / `_M` / `_L`** — **S**mall, **M**edium, **L**arge: within a bit-width, how many
  of the *sensitive* tensors (attention, the output layer) are kept at higher precision.
  `Q3_K_S < Q3_K_M < Q3_K_L` in both size **and** quality.

So `Q3_K_L` is "3-bit K-quant, large variant" — bigger and better than `Q3_K_S`, smaller
and worse than `Q4_K_M`. The size ladder for an 8B model, roughly:

```
Q2_K  ~3.0 GB   ── lowest quality, smallest
Q3_K_S ~3.6 GB
Q3_K_M ~3.9 GB
Q3_K_L ~4.0 GB
Q4_K_M ~4.9 GB  ── the usual "good default"
Q8_0  ~8.5 GB   ── near-lossless, rarely worth it locally
FP16  ~16 GB    ── unquantized
```

**The trade-off in one sentence:** more bits = closer to the original model (higher
quality) but more bytes (more memory, slower) — and on a memory-constrained machine the
bytes decide whether the model *runs at all*, which dominates the quality question.

---

## 2. The local-LLM stack — where the quant choice bites

A request from mu travels down this stack. The quant choice changes the cost at **every**
layer, but it becomes a hard wall at the GPU layer.

```
 ┌──────────────────────────────────────────────────────────────┐
 │ mu agent  (src/mu/agent.py)                                    │  picks the model,
 │   builds the prompt, parses tool calls, runs build/test gates  │  drives the loop
 ├──────────────────────────────────────────────────────────────┤
 │ mu client (src/mu/client.py)                                   │  HTTP → :1234
 │   POST /v1/chat/completions  {model, messages, num_ctx, …}     │  OpenAI-compatible
 ├──────────────────────────────────────────────────────────────┤
 │ LM Studio server  (localhost:1234)                             │  OpenAI API facade,
 │   model load/unload, JIT, request queue                        │  model manager
 ├──────────────────────────────────────────────────────────────┤
 │ llama.cpp + Metal  (the inference engine)                      │  ← QUANT LIVES HERE
 │   • mmap the GGUF weights                                       │
 │   • allocate KV cache + compute buffers on the GPU             │
 │   • run the forward pass (de-quantize on the fly, matmul)      │
 ├──────────────────────────────────────────────────────────────┤
 │ GGUF file on disk  (~/.lmstudio/models/…/*.gguf)               │  the quantized weights
 └──────────────────────────────────────────────────────────────┘
       Apple M2: CPU + GPU share ONE 8 GB unified-memory pool
```

Two facts about this host make quant size decisive:

1. **Unified memory.** On Apple Silicon the CPU and GPU share the *same* 8 GB. There is no
   separate VRAM — the model, the OS, mu's Python, and the dotnet/node build subprocesses
   all draw from one pool.
2. **mmap, not mlock.** LM Studio memory-maps the GGUF (it does **not** lock it). So the
   weight pages are *file-backed* and the OS can evict them under pressure without writing
   to swap — they re-read from the `.gguf`. This is why, in our runs, **swap was never the
   weights**; it was anonymous memory (the KV cache + the build tools' heaps).

---

## 3. How quant size affects execution — the chain

Quant size propagates through four distinct costs. The first two are obvious; the third is
the one that bit us; the fourth is the reason we cared at all.

### (a) Disk and load time
Bigger quant → bigger `.gguf` → more to download and mmap. Minor on a fast SSD.

### (b) Resident memory (the weights)
Bigger quant → more RAM held by the weights. On a shared 8 GB pool this directly steals
headroom from everything else. But because the weights are mmap'd (§2), this is *soft*
pressure — the OS can page them out.

### (c) GPU compute buffers — **load ≠ run** (the wall we hit)
This is the subtle one. Loading a model and *running* it allocate **different** memory:

- **Loading** maps the weights (file-backed, evictable).
- **Running** must allocate, in GPU memory, the **KV cache** (grows with context length)
  **and the compute buffers** (activations/scratch for the forward pass). These are
  *anonymous* GPU allocations that must physically fit.

So a model can **load successfully and then fail every inference** when the compute
buffers don't fit. That is exactly the LM Studio error we saw:

```
HTTP 400  { "error": "Compute error." }
```

— returned for *every* request to qwen3-8b and granite-3.3-8b at **Q3_K_L** (≈4.1 GB
resident) with full GPU offload (`--gpu max`), while the model showed "loaded
successfully." Lowering context 6000→4096 did **not** fix it: the binding constraint was
the **weight + compute buffers**, not the KV cache.

### (d) Quality
Fewer bits → more approximation error → (usually) fewer problems solved. This is the cost
you're trying to minimize — but only *after* the model clears (a)–(c). A model that can't
run has quality 0.

---

## 4. The findings, explained through the stack

### Finding 1 — Q4_K_M-7b won't load; Q3_K_L-7b is the sweet spot
The 7B at **Q4_K_M (~4.9 GB)** exceeded RAM and refused to load. Dropping one quant step to
**Q3_K_L (3.8 GB on disk, 4.09 GB resident)** fit, ran, and scored **7/10** — the best of
any model. One quant step was the difference between "best model on the host" and "doesn't
load." (The old `.zshrc`/README note "the 7B won't load on 8 GB" was true *only* of Q4_K_M.)

### Finding 2 — an 8B fails where a same-size 7B works (the ~4.1 GB GPU ceiling)
The striking result: qwen2.5-coder-**7b** Q3_K_L runs fine at **4.09 GB** resident, but
qwen3-**8b** and granite-3.3-**8b** Q3_K_L **Compute-error** at essentially the *same*
~4.1 GB file size. Why? **Compute-buffer size scales with the number of layers and
parameters, not just the file size.** The 8B has more transformer layers, so its
per-forward-pass activation + KV buffers are larger than the 7B's even when the *weights*
quantize to the same bytes. So the 8B blows the GPU budget while the 7B squeaks under it.
Empirically, the runnable ceiling on this host is **~4.1 GB resident**, and it's *tighter
for larger-parameter models*.

### Finding 3 — drop the quant, drop under the ceiling, and the 8Bs run
Re-quantizing the two failing 8Bs down to **Q3_K_S** (3.77 GB / 3.59 GB) put them **below**
the compute ceiling. At full GPU offload they then ran at full speed and boarded cleanly:
**qwen3-8b → 5.6/10, granite-3.3-8b → 2.2/10**. This is the apples-to-apples completion of
the comparison: every 8B measured at *its best quant that actually runs at full offload*.

### Finding 4 — the heavier quants still run, but only via partial offload (slow)
The Q3_K_L 8Bs *can* run with `--gpu 0.5` (half the layers on CPU): inference then uses CPU
RAM for the overflow instead of the GPU compute budget, so no Compute error — but it's
5–10× slower (CPU matmul). With a capability-first goal that's a legitimate option, but the
quality delta Q3_K_S→Q3_K_L is small and didn't justify ~10×-slower boards.

### Finding 5 — quant isn't the only RAM pressure; the build tools matter
Even within the runnable models, swap hit 10–11 GB during boards. The weights were mmap'd
(not the cause); the swap was the **KV cache + the dotnet/node build heaps** running
*alongside* the model. .NET's **server GC allocates a heap per core**, spiking multi-GB on
p10's build. Setting `DOTNET_gcServer=0` (workstation GC) + capping Node's heap let a build
coexist with the resident model instead of forcing swap — a reminder that on a shared pool,
the model is only one of several tenants.

### Finding 6 — benchmark rank ≠ rank on this task
seed-coder-8b is the **SWE-bench-Verified leader** among ~8B models, yet it scored 5.6,
*tied* with qwen3-8b and **below** the qwen-7b's 7.0 — and it went 0/5 on p3-sdl2 and
p7-flask. Headline benchmarks didn't predict performance on this multi-language, tool-using,
multi-file dojo. The model that *ran best here* won, not the one that benchmarks best.

---

## 5. Recommendation

**Pin `qwen2.5-coder-7b-instruct` at the `Q3_K_L` quant** — that bare id is what LM Studio
serves it under (it org-prefixes to `lmstudio-community/…` only when a second 7b collides;
`MU_AGENT_MODEL` is sent verbatim, so it must match `curl localhost:1234/v1/models`).

It is simultaneously (1) the **highest-scoring** model (7/10 — and capability is the
priority over speed), and (2) the **largest model that reliably runs** on this 8 GB host:
its 7B parameter count keeps the compute buffers under the ~4.1 GB ceiling at a 3-bit-large
quant, where the higher-parameter 8Bs either need a worse quant (and score lower) or only
run at crippled speed.

**The general rule this host teaches:** on 8 GB unified memory, pick the **largest model ×
highest quant whose *resident + compute* footprint stays under ~4.1 GB** — and remember
that for a fixed footprint, fewer parameters at a higher quant beats more parameters at a
lower one, because compute buffers (not just weights) have to fit in the same pool.

### Practical knobs (this host)
| Knob | Setting | Why |
|---|---|---|
| Quant | `Q3_K_L` for 7B, `Q3_K_S` for 8B | largest that stays under the ~4.1 GB compute ceiling |
| `--gpu` | `max` (full offload) | partial offload is 5–10× slower; only needed for >ceiling models |
| `MU_NUM_CTX` | `6000` | KV cache off swap (8192+ thrashes) |
| `DOTNET_gcServer` | `0` | workstation GC — stops p10's per-core heap spike from swapping |
| model id | match `/v1/models` exactly | LM Studio serves the bare name when unique, org-prefixes on collision; `MU_AGENT_MODEL` is sent verbatim |
