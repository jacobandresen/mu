# Session D findings — 2026-05-19

**Settings**: qwen3:8b, num_ctx=8096, num_thread=1, temperature=0, OLLAMA_NUM_PARALLEL=1
**Fix in effect**: Bug 8 (model eviction before warmup)

## Score

| P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|----|----|----|----|----|----|----|
| ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |

**Score: 1/7**

## Timings (seconds)

| Problem | Time | Exit | Notes |
|---------|------|------|-------|
| P1 helloworld | 626 | — | 2× combined planner timeout (300s each) |
| P2 sqlite | 627 | — | 2× combined planner timeout (300s each) |
| P3 SDL2 | 1021 | 0 | Planner timeout attempt 1; success attempt 2 |
| P4 fibonacci C# | 1228 | 1 | Planner ✓, writer timeout retry ✓, repair timeout ✗ |
| P5 go/gin | 727 | — | 2× planner timeout (360s each) |
| P6 rust | 725 | — | Planner ✓, lint repair timeout ✗ |
| P7 flask | 1357 | — | Planner ✓, app.py ✓, test file 2× writer timeout ✗ |

## Bug 9 — Combined planner timeout for simple problems with num_thread=1

**Root cause**: For `simple` complexity (P1, P2), the agent uses "combined plan+write mode" — a
single LLM call that produces both PLAN.md and the source file in one shot. The combined prompt
includes both task-planner and writer instructions, making it significantly larger than the
planner-only prompt. Combined planner timeout = 200s × 1.5 (ctxScale) = **300s**.

With `num_thread=1`, qwen3:8b generates at ~0.34 tok/s. A combined response (PLAN.md + code
= ~400–800 tokens) takes 1200–2400s at this rate — far exceeding the 300s deadline.

Session A (2026-05-18-A, same num_thread=1 setting) passed P1 in 165s and P2 in 327s because
the code at that time did not use combined planner for simple problems. The combined planner
was introduced later to improve throughput on faster hardware.

**Fix** (committed): In `detectComplexity`, skip combined mode when `ollama.NumThread() == 1`:
```go
if (complexity == "trivial" || complexity == "simple") && ollama.NumThread() != 1 {
    cfg.Combined = 1
} else {
    cfg.Combined = 0
}
```
Also added `ollama.NumThread()` exported function in `internal/ollama/client.go`.

**Impact on session D**: Fix applied after session D completed. Session E will use separate
planner + writer for P1/P2, matching session A behavior.

## Other timeout observations

**P3 SDL2** (complex, 360s planner limit): Succeeded on attempt 2 in 1021s total. The first
attempt timed out, but attempt 2 completed — suggesting the model responds faster on re-runs
once KV cache is partially warm or memory pressure stabilizes.

**P4 fibonacci C#** (complex): Planner ✓ → writer produced empty file (timeout, retry ✓) →
tests failed → repair timed out. The repair agent also uses the writer timeout (450s). With
num_thread=1 and a non-trivial repair prompt, 450s is sometimes insufficient.

**P6 rust** (complex): Planner ✓, Cargo.toml ✓, but `src/main.rs` produced near-empty output
twice, lint repair timed out. The writer for a trivial file ("Hello, world!") shouldn't need
450s, but the retry logic exhausted the budget.

**P7 flask** (hard, 480s planner): Planner ✓, app.py ✓, but test file writer timed out twice
(480s each) and was never written.

## Recommendations for session E

1. Combined planner disabled for num_thread=1 (done) → P1/P2 should pass like session A
2. Planner timeouts (300s simple, 360s complex) are borderline adequate — sometimes one
   attempt times out but the second succeeds
3. Repair and writer retry timeouts (450s complex) are the next bottleneck: P4/P6/P7 all
   failed due to repair or retry-writer timeout
4. Expected session E score: 3–5/7 (P1 ✓, P2 ✓, P3 ✓, P4 ?, P5 ?, P6 ?, P7 ?)
