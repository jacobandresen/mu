# Session A findings — 2026-05-18

**Settings**: qwen3:8b, num_ctx=8096, num_thread=1, temperature=0, OLLAMA_NUM_PARALLEL=1

## Score

Session A was stopped after P5 — P6 and P7 were not run (num_thread=1 slowdown made further runs impractical).

| P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|----|----|----|----|----|----|----|
| ✅ | ✅ | ✅ | ❌ | ❌ | ? | ? |

**Score: 3/5 run**

## Timings (seconds)

| Problem | Time | Exit |
|---------|------|------|
| P1 helloworld | 165 | 0 |
| P2 sqlite | 327 | 0 |
| P3 SDL2 | 928 | 0 (repair succeeded via FixDuplicateVar sensor) |
| P4 fibonacci C# | 1417 (hung, 120s timeout fired) | 1 |
| P5 Go/Gin | 225 | 1 (gin v1.9.2 hallucination) |
| P6 Rust | not run | — |
| P7 Flask | not run | — |

Comparison: previous run (num_ctx=4096, default threads): P1=64s, P3=155s, P4=127s.

## Bug 1 — num_thread=1 causes 5–10× slowdown

**Setting**: `MU_NUM_THREAD=1` (passed as `num_thread=1` in Ollama options and model params)

**Effect**: P3 took 928s vs 155s at default threads = 6× slower. P1 165s vs 64s = 2.6× slower.

On Apple Silicon M2, model inference runs on Metal GPU. `num_thread` controls CPU threads.
Setting it to 1 forces sequential CPU processing for non-GPU work, dramatically reducing throughput.

**Fix**: Leave `MU_NUM_THREAD` unset (0 = auto). See TUNING.md for full analysis.

**Implemented**: `numThread()` in client.go reads `MU_NUM_THREAD` — if unset, no `num_thread`
option is passed (ollama defaults to auto). Documented in TUNING.md.

## Bug 2 — runTests() has no timeout → interactive programs hang forever

**Observed**: P4 fibonacci C# — model wrote Program.cs that calls `Console.ReadLine()` in an
infinite loop. `dotnet run` receives EOF from stdin, returns null, and the while-loop spins
at 99% CPU forever. `runTests()` called `c.Run()` with no timeout → process never exits.

**Root cause**: `runTests()` used `exec.Command("bash", "-c", cmd)` and `c.Run()` with no
context or deadline.

**Fix** (committed): Added `context.WithTimeout(context.Background(), 120*time.Second)` to
`runTests()`. Interactive programs now fail after 120 s rather than hanging indefinitely.

## Bug 3 — Model writes interactive programs for non-interactive goals

**Observed**: P4 fibonacci — model wrote `Console.ReadLine()` loop asking "Enter the number
of terms:" even though the goal was just "write the fibonacci sequence". The test runs
non-interactively (stdin = EOF) so the program spins.

**Fix**: 
1. Added "No interactive stdin" rule to `skills/task-planner/SKILL.md` — explicitly forbids
   `Console.ReadLine`, `input()`, `scanf()` unless goal says "interactive".
2. Added same rule to `buildAutonomousSystem()` writer prompt in agent.go.

## Bug 4 — Makefile duplicate variable definition (SDL2)

**Observed**: P3 Makefile — model wrote `LDFLAGS` twice:
```
LDFLAGS = $(shell sdl2-config --libs) -Wall -Wextra -O2
LDFLAGS = $(shell sdl2-config --ldflags) -lm   # WRONG: --ldflags does not exist
```
The second assignment overwrote the first with an invalid command, causing linker errors.
The repair step timed out but the agent had already applied the fix (editing the Makefile).

**Fix**: Added `sensors.FixDuplicateVar(f)` sensor — detects duplicate top-level variable
assignments in Makefiles and removes subsequent duplicates (keeps the first).
Wired into the Makefile post-write pipeline in agent.go.

## Recommendations for session B

1. Remove `MU_NUM_THREAD` (use GPU-default threads) → expect 3–6× faster per-problem
2. Keep `num_ctx=8096` (more context helps complex multi-file tasks)
3. Code fixes already in place: runTests timeout, FixDuplicateVar, no-stdin skill rule
