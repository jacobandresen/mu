# Plan: scaffold the p10 backend from `dotnet new` at ground time

_Implementation + test record for [TOOLS.md](../../TOOLS.md) §6.1, **focused on p10**. The
canonical "Approach A" doc; [p10-minimization](p10-minimization.md) §A.1 and
[ablations.md](../ablations.md) (the lever status + verdict) reconcile with it._

**Status: DONE — wired into `run_staged`, SDK-grounded, A/B'd; ships OPT-IN (`MU_SCAFFOLD`,
default off).** A/B verdict (2026-06-25, qwen-7b, N=15): headline null (backend_build 0/15
both arms) but a **mechanistic win** — the NU1202/NETSDK1226 restore wall clears 12/15 → 0/15,
moving the binder to model compile errors (the model ceiling). Full record: §5 below,
[`ablations.md`](../ablations.md) row, [`.mu/abl_scaffold_verdict.md`]. Other stacks (p4 xUnit,
p9 Vite/Vitest) remain deferred — see §6.

---

## 0. The p10 mechanism this targets (from the ablations)

p10's `backend_build` dies in a fixed cascade ([ablations.md](../ablations.md)):
**MSB1003** (no project) → **NU1202 / restore** (wrong TFM) → **CS0246** (no `Program`) /
**CS0101** (duplicate types) → model syntax. The meta-result: **59/61 recent p10 runs die at
restore before compiling**, because the *model* authors its own `net5.0`+EF8 csproj.

Lever status today (don't restate — this plan *relates* to it):

| Lever | Status | What it does | Relation to scaffolding |
|---|---|---|---|
| MSB1003 redirect | **SHIPPED** | ensures `dotnet test` sees a project | scaffolding makes the project exist by construction — same effect, earlier |
| TFM grounding (`fix_csharp_uninstalled_tfm`) | **UNDER TEST** | *repairs* the model's csproj TFM + adds `AllowMissingPrunePackageData` | the **repair-side substitute** for scaffolding's **prevent-side** ownership — A/B one against the other, never stacked |
| entry-point task | **PARKED** behind NU1202 | injects a `Program.cs` task | scaffolding emits `Program.cs` structurally; both are downstream of the wall |
| S2 cross-stage types | **PARKED** behind NU1202 | dedups CS0101/CS0053 | scaffolding clears the wall → **S2 becomes reachable/testable** |

**The thesis:** scaffolding owns the backend *structure* (csproj TFM + `Program.cs`) so the
model never authors the file that fails restore. It does not outrank S2 — it **sequences**
the work: clearing the restore wall is the prerequisite that lets S2 (and the entry-point
lever) finally fire. Whether prevent (scaffold) beats repair (TFM-grounding) is the A/B (§5).

---

## 1. What is built (all shipped)

| Built & tested | Where |
|---|---|
| Recipes, stage-aware `detect(sig, stage=…)`, graceful `scaffold()` runner, flags (`MU_SCAFFOLD`, `_ONLINE`, `_STACKS`) | [`scaffold.py`](../../src/mu/scaffold.py) |
| `reconcile_provided()` — marks scaffold-owned files done (the shared **S3** routine) | [`agent.py`](../../src/mu/agent.py) |
| **Wiring** — `_stage_scaffold` builds a `Signal` (goal + plan + `toolchain.available()`) and `run_staged` calls `scaffold()` before the writer, threading owned files to `reconcile_provided`; `meta.json.scaffold` records the recipe | [`agent.py`](../../src/mu/agent.py) `run_staged` |
| **D1/D2/D3 webapi `post`** — SDK-grounded prune-prop (D1, net9+), unpinned EF add (D2), `Program.cs` model-owned (D3) | [`scaffold.py`](../../src/mu/scaffold.py) `_webapi_post` |
| Unit tests: detection/stage generality, offline guarantee, scoping, graceful degradation, D1 grounding, D2 add/degrade, owned-path/plan-name match, honesty boundary | `tests/test_scaffold.py`, `tests/test_reconcile.py` |

The two bugs the first wiring hit are fixed and regression-tested: the frontend stage is no
longer captured by `dotnet-webapi` (stage map), and the architect files p10's .NET project
under the **model** stage, where dotnet recipes are now eligible (the empirical fix that made
scaffolding actually fire — without it `meta.scaffold` stayed null).

---

## 2. The p10 recipe crux — empirically grounded

Verified on this host (.NET **10.0.109**), `dotnet new` then `dotnet restore`:

- `dotnet new webapi` → `net10.0` csproj, **no EF Core** (only `Microsoft.AspNetCore.OpenApi`),
  emits `Program.cs`. **It does *not* restore as-is** — fails `NETSDK1226: Prune Package data
  not found … set AllowMissingPrunePackageData to true`.
- Add `<AllowMissingPrunePackageData>true</AllowMissingPrunePackageData>` → **restores (2.1 s).**
- `dotnet add package Microsoft.EntityFrameworkCore.Sqlite` then restore → **works** (warm cache).
- `dotnet new xunit` → `net10.0`, **restores clean as-is** — and *still* restores clean after
  `dotnet add package Microsoft.AspNetCore.Mvc.Testing` (p10's real test topology, which targets
  `WebApplicationFactory<Program>`). The `NETSDK1226` trigger is the **`Microsoft.NET.Sdk.Web`**
  SDK of the webapi project, *not* an AspNetCore package reference — a plain-`Sdk` test project
  carrying the same reference is unaffected (verified on this host).

So the **xunit** (test-project) recipe is good as-is; only the **webapi** (backend) recipe is *not*.
Three decisions follow — each a real change, each validated by a unit test (§5) and the A/B:

- **D1 — the webapi recipe must patch the csproj.** A `Recipe.command` is a single argv tuple;
  it cannot also inject a property. Either extend `Recipe` to a post-scaffold step or add a
  `csproj_props` field that writes `AllowMissingPrunePackageData=true` after `dotnet new`. The
  patch targets the **`Microsoft.NET.Sdk.Web`** project specifically (the verified `NETSDK1226`
  trigger) — *not* every csproj, so the xunit project is left untouched.
  **It is the same fix `fix_csharp_uninstalled_tfm` applies** — prevent vs. repair.
  *Recommended default:* add the property; it is a no-op where prune data is present.
- **D2 — EF packages.** The blog needs EF Core + SQLite, which `dotnet new webapi` omits.
  Have the webapi recipe (when the goal signals EF/SQLite) `dotnet add package` the implied
  packages, letting the resolver pick the version (recommend pinning to the installed SDK's
  major rather than hard-coding EF 8 — *not yet measured*, so a default, not a verified fact).
  Honesty holds: the trigger is the goal's named stack, never the problem id. *Offline caveat:* §4.
- **D3 — `Program.cs` ownership.** The recipe `owns=("*.csproj",)` only, so the template's
  `Program.cs` is created-but-not-owned → the model can overwrite it and re-open CS0246. But
  the model legitimately needs to register the DbContext (`builder.Services.AddDbContext`).
  *Recommended:* keep `Program.cs` a **task** (model owns the body) but leave the scaffold's
  host bootstrap in place per the reconciliation rule — the model edits, doesn't recreate.
  The A/B's mechanistic check (§5) tells us if CS0246 actually recurs.

---

## 3. Implementation (against the tree)

1. **Build a `Signal`** from the goal, parsed plan (`test_command`, `files`) and detected
   toolchains, then call `scaffold(sig, stage=…)` at the top of each stage in
   [`run_staged`](../../src/mu/agent.py):2180, **before** the stage's `run()` — p10 is a
   staged backend→frontend goal. **Marking owned files done is largely free already:** the
   existing `reconcile_provided(…, owned_paths=None)` at agent.py:701 auto-marks any
   on-disk non-empty planned file, and scaffolded files are exactly that — so explicit
   `owned_paths=set(result.files)` threading is a precision *enhancement* (mark only what the
   scaffold owns, even if empty/unplanned), not a prerequisite for the wiring to work.
   Off-path (`MU_SCAFFOLD` unset) stays byte-identical — every guard already exists in `scaffold()`.
2. **Make `detect()` stage-aware** — `detect(sig, stage=None)`, restricting eligible recipes
   per stage (`backend → dotnet-webapi, dotnet-xunit`; `frontend → vite-vitest`) so the
   frontend stage is not captured by `dotnet-webapi`. p10's backend stage needs **both** the
   webapi project and an xunit test project.
3. **Land D1/D2** on the `dotnet-webapi` recipe (csproj patch + EF add-package step).
4. **Record** `meta.json.scaffold = {recipe, tier, files}` so analysis separates scaffolded
   from from-scratch passes and the rung is labelled **L2** (§6, honesty).

---

## 4. Offline honesty (the caveat the runs exposed)

Scaffolding fixes the **TFM-mismatch** cause of NU1202 (owns net10) and, with D1, the
**prune-data** cause (`NETSDK1226`). It does **not** fix the **cold-cache** cause: D2's
`dotnet add package` and the restore still need EF/SQLite in the local NuGet cache. Air-gapped
with a cold cache they fail — so the recipe **degrades**: `_webapi_post` returns `False`, and
the run falls back to the baseline. Concretely, the EF-less csproj is then rewritten by
`ground_plan` (plan.py) into the model-baseline EF project, so the slice runs as if
un-scaffolded — *degrade ≈ baseline*, not "the scaffold's host survives" (an earlier draft
overstated this; verified: `ground_plan` overwrites a needs-EF csproj that lacks EF). The
happy path is unaffected — EF present ⇒ no rewrite ⇒ the verified-restorable csproj stands —
and that is what the warm-cache A/B measures. This matches the `scaffold()` contract — *only
ever a head start, never a block.* TOOLS.md §6.1's "shrinks, not zeroes NU1202" is the honest
summary.

---

## 5. Test plan

**Unit (extend the existing 20 tests):**
- `detect(sig, stage='frontend')` does not return `dotnet-webapi`; `stage='backend'` yields
  webapi/xunit (closes the "first wiring" bug).
- wiring marks exactly the scaffold-owned files done via `reconcile_provided` (not source/tests).
- the webapi recipe's csproj contains `AllowMissingPrunePackageData` (D1) and the EF packages
  when the goal signals EF (D2), at the installed SDK major.
- offline/cold-cache: add-package failure ⇒ run continues on baseline (D2 degrade), no crash.
- honesty (already present): a synthetic generic "ASP.NET web API + EF" goal scaffolds; a
  no-stack goal does not.

**The A/B — reuse the ablations board exactly** ([ablations.md](../ablations.md) "How to add a
row"); do **not** invent a parallel harness:
- Pre-register `.mu/abl_scaffold_prereg.md` (hypothesis, flag, gates, N) **before** running.
- `mu dojo measure p10 -n 15`, single variable: `MU_SCAFFOLD=0` vs `MU_SCAFFOLD=1`
  (`MU_SCAFFOLD_STACKS=dotnet-webapi,dotnet-xunit`), fresh process per run, per-layer q̂.
- **P1 (headline):** p10 `backend_build` Δq̂ 95%-CI lower bound **> 0** ⇒ flip default-on.
- **Mechanistic secondary:** does **NU1202/NETSDK1226 drop out of the ON-arm first-error mix**?
  (the zero-LLM `nu1202_diagnosis.md` scan). This is the direct test of the §0 thesis.
- **Third arm:** `MU_SCAFFOLD=1` vs `MU_TFM_GROUNDING=1` — prevent vs. repair at the same wall
  (D1). They are substitutes; measure which clears restore more reliably, do not stack them.
- **Controls (P2, no regression):** **p4** (dotnet, recipe-eligible) and **p1/p2** (non-dotnet,
  recipe must never fire). N=15 single-problem CI ≈ ±0.165 — read a null P1 as *inconclusive*.
- Continuous corroboration (less noisy than pass/fail): median `backend_build` repair-iters and
  tokens/run should drop in the ON arm.

**KEEP iff** P1 clears and no control regresses; record the verdict as a new `ablations.md`
row. **Then** re-test the PARKED S2/entry-point levers, now that restore is reachable.

---

## 6. Overlap cleanup & scope

- **This is the canonical scaffolding plan.** [p10-min](p10-minimization.md) §A.1 ("Approach A")
  and `scaffold.py`'s wiring point back here; `reconcile_provided` is p10-min's **S3**.
- **`ablations.md` owns the empirical lever status** — referenced, not duplicated, in §0.
- **TOOLS.md §6.1 is the one-paragraph summary**; this doc is its implementation.
- **Deferred (not in the p10 push):** the `vite-vitest` online recipe + vendored fallback for
  p9, and the `dotnet-xunit`-only path for p4. Both are already in `scaffold.py`; they get
  their own A/B once p10's prevent-vs-repair question is settled.

## 7. Work breakdown

- [x] `scaffold.py`: detector + declarative recipes + graceful runner + flags.
- [x] `reconcile_provided` (S3) + 20 unit tests.
- [x] Stage-aware `detect(sig, stage=…)` (§3.2).
- [x] Wire `scaffold()` into `run_staged` behind `MU_SCAFFOLD`; pass owned files to
      `reconcile_provided` (`run(owned_paths=…)`); record `meta.json.scaffold` via
      `MU_SCAFFOLD_RECIPE`, cleared per stage so labels don't leak (§3.1/3.4).
- [x] webapi recipe D1 (`AllowMissingPrunePackageData`, scoped to `Sdk.Web`) + D2 (EF
      add-package, unpinned) via `Recipe.post`. **D3:** always own the csproj — D1 makes it
      restore regardless, so a degrade is informational, not an ownership drop (corrects the
      first sketch); `Program.cs` stays a model task via explicit `owned_paths` (§2).
- [x] Unit tests for the new behaviours + offline degrade + the owned-path/plan-name
      match (§5).
- [x] Pre-register (`.mu/abl_scaffold_prereg.md`) + run the p10 headline A/B. **Result
      (2026-06-25, qwen-7b, N=15):** headline **null** — backend_build 0/15 ON = 0/15 OFF
      (P1 CI-lo −0.166). **Mechanistic win:** NU1202/NETSDK1226 **12/15 → 0/15**, scaffold
      fired 15/15, binder moved to CS0246 + model syntax errors (CS1002/1026/1513/1519);
      repair-iters 6.0→4.0. Verdict **OPT-IN** (`ablations.md` row,
      `.mu/abl_scaffold_verdict.md`). The wall clears; the residual is the model ceiling.
- [ ] Follow-ups the result opens: re-run the PARKED entry-point + S2 A/Bs with
      `MU_SCAFFOLD=1` (compilation now reachable); the deferred p4/p1/p2 controls + Arm 3
      (vs `MU_TFM_GROUNDING`).
