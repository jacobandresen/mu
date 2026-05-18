# Session B findings — 2026-05-18

**Settings**: qwen3:8b, num_ctx=8096, num_thread=unset (auto), temperature=0, OLLAMA_NUM_PARALLEL=1

Fixes in effect from session A: runTests 120s timeout, FixDuplicateVar sensor, no-stdin skill rule.

## Score

| P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|----|----|----|----|----|----|----|
| ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |

**Score: 4/7**

## Timings (seconds)

| Problem | Time | Exit |
|---------|------|------|
| P1 helloworld | 371 | 0 |
| P2 sqlite | 329 | 0 |
| P3 SDL2 | 750 | 1 |
| P4 fibonacci C# | 412 | 0 (no-stdin fix worked) |
| P5 Go/Gin | 1351 | 1 |
| P6 Rust | 284 | 0 |
| P7 Flask | 1728 | 1 |

## Bug 5 — Go module version hallucination (gin v1.9.2)

**Observed**: P5 Go/Gin — model wrote `github.com/gin-gonic/gin v1.9.2` in go.mod. This version
does not exist (latest stable is v1.9.1). `go mod tidy` failed with:
```
go: downloading github.com/gin-gonic/gin v1.9.2
go: example.com/ping-server imports
    github.com/gin-gonic/gin: reading github.com/gin-gonic/gin/go.mod at revision v1.9.2: unknown revision v1.9.2
```

The error suppression in `FixGoMakefile` (`2>/dev/null`) hid this from the repair agent in the
first attempt. The second attempt also failed because repair didn't correct the version.

**Fix** (implemented mid-session B, applies to future runs):
1. Removed `2>/dev/null` suppression from `FixGoMakefile` in `sensors/golang.go` — errors now propagate.
2. Added `sensors.FixGoModVersions()` with `knownVersions` map: `gin → v1.9.1`.
   Wired into go.mod post-write pipeline in agent.go.

**Impact on session B**: FixGoModVersions was added after P5 had already been written, so P5 still
failed. Future sessions will have the correction applied at write time.

## Bug 6 — Premature test gate fires before Makefile is written

**Observed**: P7 Flask — the planner ordered files as `app.py → tests/test_app.py → Makefile`.
After writing `tests/test_app.py` (iteration 2), the test gate ran `make test`, which failed
with "No rule to make target 'test'" because the Makefile was iteration 3 (not yet written).
The repair agent hit max turns and gave up, never reaching the Makefile iteration.

**Root cause**: The inter-iteration test gate checked `isTestFile(task.FilePath)` but did not
check whether any build file (Makefile) was still pending in the plan.

**Fix** (implemented mid-session B, applies to future runs):
Added `plan.HasPendingBuildFile(p)` — the test gate now skips if any build file remains unwritten:
```go
if testCmd != "" && isTestFile(task.FilePath) && !plan.HasPendingBuildFile(p) {
```

**Impact on session B**: Fix was added after P7 started, so P7 still failed. Future sessions will
skip the premature gate.

## Bug 7 — Repair rewrites Makefile, re-introducing broken LDFLAGS (SDL2)

**Observed**: P3 SDL2 — the FixDuplicateVar sensor correctly removed the duplicate `LDFLAGS`
assignment at write time. However, the repair agent subsequently rewrote the Makefile with the
full duplicated content again (both a correct `LDFLAGS=$(shell sdl2-config --libs)` and a
wrong `LDFLAGS=$(shell sdl2-config --ldflags)`). FixDuplicateVar does not run during repair.
The wrong LDFLAGS definition (using `--ldflags` which doesn't exist) overrode the correct one,
causing SDL2 symbols to go unresolved.

**Fix**: FixDuplicateVar only covers simple duplicate variable assignments. The repair output
shows the model duplicated the entire Makefile body. A more robust fix would be to also run
sensors on repair output before testing. Logged for future implementation.

## Improvements vs session A (with num_thread=1)

| Problem | Session A | Session B | Delta |
|---------|-----------|-----------|-------|
| P1 | ✓ 165s | ✓ 371s | +206s (longer — was suspiciously fast) |
| P2 | ✓ 327s | ✓ 329s | same |
| P3 | ✓ 928s | ✗ 750s | -178s but now failing |
| P4 | ✗ 1417s | ✓ 412s | **no-stdin fix worked** |
| P5 | ✗ 225s | ✗ 1351s | worse (repair runs longer) |

P4 is the clear win: the no-stdin rule + runTests timeout turned a hang into a correct solution.
