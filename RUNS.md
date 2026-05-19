# Runs

Timing in seconds per problem. **X** = failed. **?** = not run.

| Run | Score | P1 helloworld | P2 sqlite | P3 sdl2 | P4 fibonacci | P5 go/gin | P6 rust | P7 flask |
|-----|-------|--------------|-----------|---------|--------------|-----------|---------|----------|
| [2026-05-17](dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17/) (v0.3, pi loop) | 6/7 | 113 | 310 | 271 | 149 | 193 | 383 | X |
| [2026-05-17-A](dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-17-A/) (v0.4 native Go, baseline) | 2/7 | ✓ | X | ✓ | X | X | X | X |
| [2026-05-18](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18/) (v0.4 native Go) | 3/7 | 64 | X 271 | 155 | 127 | X 168 | X 252 | X ~170 |
| [2026-05-18-A](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18-A/) (num_thread=1, stopped after P5) | 3/5 | 165 | 327 | 928 | X 1417 | X 225 | ? | ? |
| [2026-05-18-B](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18-B/) (num_thread=auto, bugs fixed) | 4/7 | 371 | 329 | X 750 | 412 | X 1351 | 284 | X 1728 |
| [2026-05-19](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19/) (num_thread=1, MCP model competing for RAM) | 0/7 | X 482 | X 520 | X 62 | X 71 | X 69 | X 62 | X 72 |
| [2026-05-19-B](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-B/) (num_thread=1, eviction fix applied) | 1/7 | X 626 | X 627 | 1021 | X 1228 | X 727 | X 725 | X 1357 |
| [2026-05-19-E](dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-E/) (num_thread=1, eviction+combined fixes) | 2/7 | 269 | X 903 | X 815 | 569 | X 1142 | X 1082 | X 826 |
