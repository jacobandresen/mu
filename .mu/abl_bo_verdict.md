# MU_BUILD_ORDER A/B result — plan Step 0.6 / S6

model `qwen2.5-coder-7b-instruct` · N per arm as recorded


| problem | ON | OFF | Δpass | 95% CI | Δrepair-iters |
|---|---|---|---|---|---|
| p1-helloworld (control) | 15/15 | 15/15 | +0.001 | [-0.163, +0.168] | +0.00 |
| p2-sqlite | 14/15 | 13/15 | +0.059 | [-0.173, +0.298] | +0.40 |
| p3-sdl2 | 15/15 | 15/15 | +0.000 | [-0.165, +0.164] | +0.93 |

**ΔE[#solved] = +0.060  95% CI [-0.258, +0.381]**

## Verdict

- P1 (ΔE[#solved] CI lo > 0): FAIL (lo=-0.258)
- P2 (no problem regressed): PASS

**NO pass-rate lift on these easy problems (expected, prereg) — stays opt-in; check the Δrepair-iters column for the efficiency story, and re-test on hard multi-layer goals once p10 builds**
