# Session C findings — 2026-05-19

**Settings**: qwen3:8b, num_ctx=8096, num_thread=1, temperature=0, OLLAMA_NUM_PARALLEL=1

## Score

| P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|----|----|----|----|----|----|----|
| ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Score: 0/7** — complete failure

## Timings (seconds)

| Problem | Time | Exit | Mode |
|---------|------|------|------|
| P1 helloworld | 482 | — | 2× planner timeout (300s each) |
| P2 sqlite | 520 | — | 2× planner timeout (300s each) |
| P3 SDL2 | 62 | — | 2× fast API error (~31s each) |
| P4 fibonacci | 71 | — | 2× fast API error (~35s each) |
| P5 go/gin | 69 | — | 2× fast API error (~34s each) |
| P6 rust | 62 | — | 2× fast API error (~31s each) |
| P7 flask | 72 | — | 2× fast API error (~36s each) |

## Root Cause: Model Memory Competition

**Hardware**: M2 8 GB unified memory.

The MCP server (Claude Code's ollama MCP tool) keeps `qwen2.5-coder:agent` loaded permanently
for its own inference (5.1 GB RSS). When the dojo warmup tries to load `qwen3:agent` (5.2 GB),
total requirement is ~10.3 GB — exceeding physical RAM by 2.3 GB. Extreme swapping results.

With `num_thread=1`, swapping is catastrophic because a single CPU thread handles all memory
prefetch, tokenization, and weight loading. Model cold-load with num_thread=1 from a swapping
state can take 300–500 seconds, exceeding planner timeouts.

### Failure mode breakdown

**P1–P2** (482s, 520s): Planner attempted API calls, each timed out after 300s (1.5× of 200s
base for simple). Two attempts per problem → ~520s total. The model was partially loading or
swapping so heavily that no response arrived before the 300s deadline.

**P3–P7** (62–72s): After P1/P2 exhausted all retries, the system was in a degraded state.
API calls returned quickly with errors (connection reset / OOM response) rather than timing out.
"No PLAN.md produced" in ~31–36s per attempt = the API returned but produced no usable output.

## Bug 8 — run.sh warmup does not evict competing models

**Root cause**: `run.sh` warmed up the target model without first evicting other loaded models.
On an 8 GB machine where the MCP server keeps a 5 GB model loaded, adding another 5 GB model
causes OOM swapping.

**Fix** (committed to `dojo/run.sh`): Before each warmup, enumerate loaded models via
`GET /api/ps` and unload each with `keep_alive=0`. This guarantees the target model loads into
clean memory:
```zsh
curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(m['name'])
" | while read -r model; do
    curl -s -m 30 -X POST http://localhost:11434/api/generate \
        -d "{\"model\":\"$model\",\"keep_alive\":0}" -o /dev/null || true
done
```

Also increased warmup curl timeout from 120s → 300s to account for cold model load time
on constrained hardware.

## Note on num_thread=1 vs previous session A

Session A (2026-05-18) also used num_thread=1 and scored 3/5 (P1 in 165s, P3 in 928s).
Session C scored 0/7 for a different reason: the MCP server was not competing for memory
in session A (or its model had already been evicted). The eviction fix will isolate the dojo
from MCP interference, allowing session D to test num_thread=1 cleanly.

## Recommendations for session D

1. Apply eviction fix in run.sh (done) → qwen3:agent gets full 8 GB
2. Keep num_thread=1 per user instructions — session A showed it works (slowly) without interference
3. Expect session D timings to be similar to session A: P1 ~165s, P3 ~928s, etc.
