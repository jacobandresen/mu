# Runs

Timing in seconds per problem. **X** = failed. **?** = not run.

| Run | Score | P1 helloworld | P2 sqlite | P3 sdl2 | P4 fibonacci | P5 go/gin | P6 rust | P7 flask |
|-----|-------|--------------|-----------|---------|--------------|-----------|---------|----------|
| [2026-05-17](dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17/) (v0.3, pi loop) | 6/7 | 113 | 310 | 271 | 149 | 193 | 383 | X |
| [2026-05-18-B](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18-B/) (v0.4, num_thread=auto) | 4/7 | 371 | 329 | X 750 | 412 | X 1351 | 284 | X 1728 |
| [2026-05-19-E](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-E/) (v0.4, num_thread=1, eviction+combined fixes) | 2/7 | 269 | X 903 | X 815 | 569 | X 1142 | X 1082 | X 826 |
| [2026-05-20](dojo/claude-qwen3-8b-macos-m2-8gb-v0.5.0-2026-05-20/) (v0.5) | 4/7 | 60 | 323 | X 591 | 189 | X 401 | 135 | X 780 |
| [2026-05-21](dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-21/) (v0.5, gemma4:e2b, run 1) | 3/7 | 35 | X 424 | X 177 | X 78 | 16 | 23 | X 325 |
| [2026-05-21-B](dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-21-B/) (v0.5, gemma4:e2b, run 2, SDL2+csproj sensors) | 5/7 | 20 | X 223 | 49 | 21 | 14 | 17 | X 173 |
| [2026-05-21-C](dojo/claude-gemma4-e2b-macos-m2-8gb-v0.5.0-2026-05-21-C/) (v0.5, gemma4:e2b, run 3, all sensors) | ? | ? | ? | ? | ? | ? | ? | ? |
