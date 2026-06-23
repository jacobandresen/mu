# S2 ablation result — plan Step 0.3 KEEP gate

model `qwen2.5-coder-7b-instruct` · level L0 (I3)


## p10-dotnet-vue-blog — per-layer q̂ (ON = S2 enabled)

| layer | ON clears | OFF clears | Δq̂ (ON−OFF) | 95% CI |
|---|---|---|---|---|
| backend_build **←gate** | 0/15 | 0/15 | -0.001 | [-0.166, +0.164] |
| backend_test | 0/15 | 0/15 | -0.000 | [-0.164, +0.165] |
| frontend_build | 0/15 | 0/15 | -0.000 | [-0.166, +0.162] |
| frontend_test | 0/15 | 0/15 | -0.001 | [-0.166, +0.166] |

p_solve: ON 0.0 vs OFF 0.0 · pass-rate ON 0.00 vs OFF 0.00 · repair-iters ON 0.0 vs OFF 0.4

## p4 (control / coverage) — pass-rate

ON 15/15 (1.00) vs OFF 14/15 (0.93) · Δ +0.059 CI [-0.123, +0.258]
control gate (point Δ ≥ −0.05 ∧ no proven harm): PASS · strict §4.1 (CI lo ≥ −0.05, underpowered at N=15): n/a

## Verdict

- Gate 1 (p10 backend_build Δq̂ CI lo > 0, the headline): FAIL (lo=-0.166)
- Gate 2 (p4 control: no observed/proven regression): PASS

**DROP to disabled-by-default (behind the ablation flag)**
