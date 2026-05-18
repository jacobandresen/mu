# Runs

Timing in seconds per problem. **X** = failed. **?** = not run.

| Run | Score | P1 helloworld | P2 sqlite | P3 sdl2 | P4 fibonacci | P5 go/gin | P6 rust | P7 flask |
|-----|-------|--------------|-----------|---------|--------------|-----------|---------|----------|
| [2026-05-17](dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17/) (v0.3, pi loop) | 6/7 | 113 | 310 | 271 | 149 | 193 | 383 | X |
| [2026-05-17-A](dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17-A/) (v0.4 native Go, baseline) | 2/7 | ✓ | X | ✓ | X | X | X | X |
| [2026-05-18](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18/) (v0.4 native Go) | 3/7 | 64 | X 271 | 155 | 127 | X 168 | X 252 | X ~170 |
| [2026-05-18-A](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18-A/) (num_thread=1, stopped after P5) | 3/5 | 165 | 327 | 928 | X 1417 | X 225 | ? | ? |
| [2026-05-18-B](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18-B/) (num_thread=auto, bugs fixed) | 4/7 | 371 | 329 | X 750 | 412 | X 1351 | 284 | X 1728 |
