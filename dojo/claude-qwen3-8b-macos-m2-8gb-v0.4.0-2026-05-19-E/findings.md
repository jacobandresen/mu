# Session E findings — 2026-05-19

**Settings**: qwen3:8b, num_ctx=8096, num_thread=1, temperature=0, OLLAMA_NUM_PARALLEL=1
**Fixes in effect**: Bug 8 (model eviction before warmup), Bug 9 (combined mode disabled for num_thread=1)

## Score

| P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|----|----|----|----|----|----|----|
| ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

**Score: 2/7**

## Timings (seconds)

| Problem | Time | Exit | Notes |
|---------|------|------|-------|
| P1 helloworld | 269 | 0 | Near-empty retry; second write passed lint |
| P2 sqlite | 903 | — | Planner ✓, writer timed out twice (330s each) |
| P3 SDL2 | 815 | — | Planner ✓, writer ✓, tests failed, repair timed out (450s) |
| P4 fibonacci C# | 569 | 0 | Planner ✓, writer ✓, tests passed |
| P5 go/gin | 1142 | — | Planner ✓, writers ✓, tests failed, repair timed out (450s) |
| P6 rust | 1082 | — | Near-empty retry, lint repair timed out (450s) |
| P7 flask | 826 | — | Planner ✓, app.py ✓, test file writer got EOF (interrupted) |

## Bug 10 — No thread-based timeout scaling

**Root cause**: The existing `ctxScale` multiplier (1.5× when num_ctx ≥ 8000) accounts for
large-context memory pressure but not for CPU thread limitation. With `num_thread=1`,
Apple Silicon routes all inference through a single CPU thread — 5–10× slower than auto
(GPU Metal) mode. The resulting effective throughput is ~1–2 tok/s, but timeouts were sized
for ~8 tok/s (auto threads at 8096 ctx).

**Failure pattern (all 5 failures)**:
- P2: writer_simple timeout = 220 × 1.5 = 330s; todo.py (~600 tokens) requires ~300–600s at 1–2 tok/s → reliably at/over limit
- P3, P5, P6: repair_complex timeout = 300 × 1.5 = 450s; repair prompts are larger than plain writes → consistent timeout
- P7: Interrupted during second writer attempt

**Comparison with session A (same num_thread=1, same 8096 ctx, score 3/5)**:
Session A used combined plan+write mode for simple tasks. Combined mode produced PLAN.md +
todo.py in a single API call with a combined prompt structure that fit within the 300s planner
timeout. Session E disabled combined mode (Bug 9 fix) and exposed the separate writer timeout
as insufficient.

**Fix** (committed): Multiply `ctxScale` by 2.0 when `num_thread==1`:
```go
if ollama.NumThread() == 1 {
    ctxScale *= 2.0
}
```
With 8096 ctx + num_thread=1: ctxScale = 1.5 × 2.0 = 3.0
- writer_simple = 220 × 3.0 = 660s
- writer_complex = 300 × 3.0 = 900s
- planner_simple = 200 × 3.0 = 600s
- planner_complex = 360 × 3.0 = 1080s

With 6000 ctx + num_thread=1: ctxScale = 1.0 × 2.0 = 2.0
- writer_simple = 220 × 2.0 = 440s
- writer_complex = 300 × 2.0 = 600s

**Also fixed**: `dojo/run.sh` now defaults `MU_NUM_CTX=6000` (was implicitly 4096 when unset;
sessions C/D/E ran with externally-set 8096). Per TUNING.md, 6000 is the sweet spot for M2 8 GB:
~450 MB KV cache vs ~600 MB at 8096, meaningfully less swap pressure and faster inference.

## Recommendations for session F

1. Thread-scale fix applied → timeouts 2× larger for num_thread=1
2. `run.sh` now defaults MU_NUM_CTX=6000 → less swap, faster inference (no ctxScale)
3. Combined timeouts (2.0× at 6000 ctx): writer_simple=440s, repair_complex=600s — comfortable
4. Expected score: 5–6/7 if timeouts were the only blocking issue
