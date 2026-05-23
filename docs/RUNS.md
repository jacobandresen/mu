# Runs

Timing in seconds per problem. **X** = failed.

Only milestone runs are kept in `dojo/`; all rows remain as historical record.

| Run | Score | P1 helloworld | P2 sqlite | P3 sdl2 | P4 fibonacci | P5 go/gin | P6 rust | P7 flask |
|-----|-------|--------------|-----------|---------|--------------|-----------|---------|----------|
| [2026-05-17](../dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17/) (v0.3, qwen3:8b, pi loop) | **6/7** | 113 | 310 | 271 | 149 | 193 | 383 | X |
| 2026-05-18-B (v0.4, qwen3:8b, num_thread=auto) | 4/7 | 371 | 329 | X 750 | 412 | X 1351 | 284 | X 1728 |
| 2026-05-19-E (v0.4, qwen3:8b, num_thread=1, eviction+combined fixes) | 2/7 | 269 | X 903 | X 815 | 569 | X 1142 | X 1082 | X 826 |
| 2026-05-20 (v0.5, qwen3:8b) | 4/7 | 60 | 323 | X 591 | 189 | X 401 | 135 | X 780 |
| 2026-05-21 (v0.5, gemma4:e2b, run 1) | 3/7 | 35 | X 424 | X 177 | X 78 | 16 | 23 | X 325 |
| 2026-05-21-B (v0.5, gemma4:e2b, run 2, SDL2+csproj sensors) | **5/7** | 20 | X 223 | 49 | 21 | 14 | 17 | X 173 |
| 2026-05-21-C (v0.5, gemma4:e2b, run 3, all sensors) | 4/7 | 16 | X 810 | X 59 | 19 | 14 | 16 | X 324 |
| 2026-05-21-D (v0.5, gemma4:e2b, run 4, +SpaceIndent+SDLDestroy+CodeExtract) | **5/7** | 17 | X 242 | 42 | 18 | 13 | 16 | X 281 |
| 2026-05-21-E (v0.5, gemma4:e2b, run 5, +OrphanFix+WriterRetry) | 4/7 | 16 | X 260 | X 60 | 18 | 13 | 16 | X 255 |
| 2026-05-21-F (v0.5, gemma4:e2b, run 6, +WriterToolDefs+SDL2InlineRecipe) | 4/7 | 15 | X 242 | X 60 | 17 | 13 | 16 | X 270 |
| 2026-05-21 (v0.5, qwen3:4b-instruct) | 4/7 | 9 | X 436 | X 74 | 27 | 26 | 18 | X 240 |
| 2026-05-21 (v0.5, qwen3:8b, +WriterToolDefs) | 4/7 | 58 | X 906 | 508 | 174 | X 289 | 149 | X drop |
| 2026-05-22 (v0.5, gemma4:e2b, run 7, +DuplicateAll+reapplyMakefile) | 4/7 | 19 | X 228 | X 86 | 19 | 13 | 16 | X 287 |
| [2026-05-22](../dojo/claude-qwen3-8b-macos-m2-8gb-v0.6.0-2026-05-22/) (v0.6, qwen3:8b, **honest harness**, no plan-gen/sensors, num_ctx=8192) | **1/7** | 158 | X 1514 | X 256 | X 313 | X 1490 | X 195 | X 123 |
| 2026-05-23 (v0.6.1, qwen3:8b, honest harness + repair loop, num_ctx=8192) | **2/7** | 138 | X 1640 | X 333 | X 608 | X 698 | 170 | X 420 |
