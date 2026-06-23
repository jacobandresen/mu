# Pre-registration — MSB1003 test-command-redirect A/B (plan Step 0.5 backend_build)

Written **before** the run (I6). Capability: `plan.normalize_test_command` now
redirects `dotnet test <dir>` to the root project whenever `<dir>` resolves to no
`.csproj` (absent / a file / a csproj-less dir), instead of only when the dir already
exists. A **default-on normalizer timing fix** (commit `8f82b34`), not a runtime flag —
so the **OFF arm runs the parent commit's `src/mu/plan.py`** (`HEAD~1`), swapped in by
the orchestrator; the ON arm runs `HEAD`.

**Model:** `qwen2.5-coder-7b-instruct`, ctx 6000, fresh plan each run, unseeded.

**Arms (N=15 each):** ON = fix in place; OFF = pre-fix `plan.py`.
- **Headline — p10-dotnet-vue-blog** (staged; per-layer q̂). The 7b bottleneck is
  `backend_build` (q̂≈0.14), whose dominant first error is **MSB1003 ×8/12** (archive
  scan 2026-06-23): `dotnet test tests/` against a single-project layout with no
  `tests/*.csproj`.
- **Control — p4-fibonacci** (`dotnet`, currently ~4/5). Must not regress; the only
  other dotnet problem, so it exercises the same normalizer path.

**Statistic:** Δ = ON − OFF. Per-arm Beta-Binomial posterior-difference sampling
(stdlib `observe.beta_binomial` prior), 60k draws.

**KEEP gate (pre-registered):**
1. **P1 (headline):** p10 `backend_build` Δq̂ (ON−OFF), 95% CI lower bound **> 0**.
2. **P2 (control):** p4 Δpass-rate no regression — point Δ ≥ −0.05 ∧ no proven harm
   (CI hi ≥ −0.05); strict §4.1 CI-lo reported but underpowered at N=15 (§4.5).

**Decision:** the fix is **retained regardless** (it's a no-regret internal-consistency
fix — grounding must not emit a test command pointing at a project it knows won't
exist). What the A/B decides is the *credit*:
- **P1∧P2 ⇒** the fix lifts `backend_build`; record an `efficacy_run` Δ, append to the
  ledger, the board's p10 bottleneck moves to the next layer/error.
- **P1 FAIL ∧ P2 PASS ⇒** MSB1003 clears but a downstream error (CS0101/CS0246) *re-binds*
  `backend_build` immediately — expected per the S2 lesson (Result 2/3: a single fix on
  a 0/L layer buys ≈nothing until every blocker in that layer is removed). Fix stays
  (no regression); **re-scan the new first-error** to aim the next lever / Phase 1 probe.
- **P2 FAIL ⇒** the redirect harms a passing dotnet problem; revert and rethink.

**Secondary (reported, not gated):** p10 p_solve, pass_rate, avg repair-iters;
**whether MSB1003 disappears** from the p10 ON gate logs (the mechanistic check that
the redirect fired).

**Honest expectation:** `backend_build` likely rises from ~0.14 but may *not* clear the
CI-lo>0 bar if CS0101/CS0246 immediately re-bind it; p4 flat. A moved bottleneck with no
regression is itself the win — it's the data that finally aims the B-probe.
