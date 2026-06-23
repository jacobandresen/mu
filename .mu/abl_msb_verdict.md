# MSB1003 redirect A/B — plan Step 0.5 backend_build

model `qwen2.5-coder-7b-instruct` · level L0 (I3) · ON = fix (HEAD) · OFF = parent `plan.py`


## p10-dotnet-vue-blog — per-layer q̂ (ON = redirect fix)

| layer | ON clears | OFF clears | Δq̂ (ON−OFF) | 95% CI |
|---|---|---|---|---|
| backend_build **←gate** | 0/15 | 0/15 | -0.001 | [-0.166, +0.164] |
| backend_test | 0/15 | 0/15 | -0.000 | [-0.164, +0.165] |
| frontend_build | 0/15 | 0/15 | -0.000 | [-0.166, +0.162] |
| frontend_test | 0/15 | 0/15 | -0.001 | [-0.166, +0.166] |

p_solve: ON 0.0 vs OFF 0.0 · pass-rate ON 0.00 vs OFF 0.00 · repair-iters ON 0.8 vs OFF 0.0

## p4-fibonacci (dotnet control) — pass-rate

ON 13/15 (0.87) vs OFF 12/15 (0.80) · Δ +0.060 CI [-0.208, +0.327]
control gate (point Δ ≥ −0.05 ∧ no proven harm): PASS · strict §4.1 (underpowered): n/a

## Verdict

- Gate 1 (p10 backend_build Δq̂ CI lo > 0): FAIL (lo=-0.166)
- Gate 2 (p4 control: no observed/proven regression): PASS

**RETAINED (no-regret) — MSB1003 cleared but backend_build did not clear the CI bar: a downstream error (CS0101/CS0246) re-binds it (expected, S2 lesson). Re-scan the new first-error to aim the next lever / Phase 1 probe.**
