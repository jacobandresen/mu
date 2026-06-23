# Machine-move handoff — 2026-06-23

Branch **`machine-move-handoff`** is a self-contained snapshot for resuming the p10
minimization work (`docs/plans/p10-minimization.md`) on another machine. It carries
everything `main` has **plus** the normally-gitignored experiment artifacts under
`.mu/` (force-added here) and this guide.

> **First thing on the new machine:** read this file top to bottom, run the
> **Setup checklist**, then the **Resume** section.

---

## TL;DR — where things stand

The p10 `backend_build` bottleneck (q̂≈0.14, the dojo's one 0-pass problem) was
diagnosed and partly attacked this session:

1. **MSB1003 fix — SHIPPED + PROVEN-MECHANICAL** (`8f82b34`). The model wrote
   `dotnet test tests/` against a single-project layout with no `tests/*.csproj`;
   `normalize_test_command`'s redirect was guarded on `arg_path.is_dir()` and ran at
   grounding time (before `tests/` exists), so it no-oped. Fixed to fire whenever
   `<dir>` resolves to no `.csproj`. A/B (`.mu/abl_msb_verdict.md`): **MSB1003
   eliminated 10/15 → 0/15**; every run now reaches compilation. `backend_build` still
   0/15 — the bottleneck **moved deeper** to CS0246 ×6 + CS0101 ×6.

2. **ASP.NET entry-point completeness — SHIPPED, UNPROVEN** (`13a81cd`, flag
   `MU_ASPNET_ENTRYPOINT`, default off). Root cause of CS0246: the architect plans
   Models/DbContext/Controllers but **never an entry point**, so `Program` doesn't
   exist and `WebApplicationFactory<Program>` can't compile. `ground_plan` now injects
   a `Program.cs` *task* (writer authors it — no pregenerated code, §0.2). **Needs an
   A/B before it can be credited.**

3. **S2 re-evaluation — WAS RUNNING when this snapshot was taken** (see In-flight).

Suite: **305 green** (`.venv/bin/python -m pytest tests/ --ignore=tests/test_interaction_model.py`;
the ignored module needs the optional `pgmpy` dep — pre-existing, unrelated).

---

## Commits carried by this branch (were unpushed on `main`)

```
13a81cd feat(plan): ASP.NET entry-point completeness in ground_plan (MU_ASPNET_ENTRYPOINT)
5eb1ac5 docs(p10 plan): Step 0.5 — MSB1003 A/B result (fix works, bottleneck moved)
8f82b34 fix(plan): redirect `dotnet test <dir>` with no project before it MSB1003s
a29bf0a feat(dojo): add p12-physics-sdl2 problem (C + SDL2 physics)
811f5a6 docs(p10 plan): Step 0.6 A/B resolved — p3-sdl2 fix verified, S6 stays opt-in
2189c32 feat(dojo): add p11-foucault-sdl2 problem (C + SDL2)
```

These are real, tested, finished work — not WIP. After verifying on the new machine,
**fast-forward `main` to this branch** (or cherry-pick) and push. Nothing here needs
to stay on a side branch except this `docs/handoff/` dir and the `.mu/` artifacts.

---

## In-flight: S2 re-evaluation (#2) — INTERRUPTED by the move

Launched on the old machine (`.mu/abl_s2b_run.sh`, detached) and **will be killed by
the move** — no arms had finalized when this snapshot was taken, so treat it as **not
run**. It re-tests whether S2 (cross-stage type reflexes, `MU_S2_TYPE_REFLEXES=1`)
lifts `backend_build` now that the MSB1003 fix makes CS0101 reachable (6/15).

- Pre-registration: `.mu/abl_s2b_prereg.md`
- Orchestrator: `.mu/abl_s2b_run.sh` (toggles only S2; entry-point held off — single
  variable). Re-run verbatim on the new machine: `nohup ./.mu/abl_s2b_run.sh &`
- Analyzer → verdict: `.mu/abl_s2b_analyze.py` → `.mu/abl_s2b_verdict.md` (runs
  automatically at the end).
- Honest expectation (from the prereg): at best a *partial* lift — CS0246 (no
  `Program`, entry-point off) still binds ~6/15, may cap P1 below CI-lo>0.

---

## Pending / unproven (the resume queue)

| Item | State | Next action |
|---|---|---|
| **MSB1003 fix** | shipped, proven-mechanical | done — keep |
| **Entry-point lever** (`MU_ASPNET_ENTRYPOINT`) | shipped, **unproven** | **A/B** on/off, p10 + p2/p4 controls. Likely the bigger `backend_build` mover than S2 (CS0246 is upstream — `Program` must exist before the test compiles) |
| **S2 re-eval** (`MU_S2_TYPE_REFLEXES`) | **not run** (interrupted) | re-run `.mu/abl_s2b_run.sh`; KEEP→flip S2 default-on, else stays opt-in |
| Phase 1 B-probe | blocked on backend_build | only after backend_build clears — aim it at the *then*-current first-error |

Recommended order on the new machine: **A/B the entry-point lever first** (dominant +
upstream), then re-run S2 with the winning entry-point setting.

---

## What does NOT travel with git — new-machine Setup checklist

Local state that is **not** in the repo and must be recreated:

- [ ] **Python venv** (`.venv/`, gitignored). Needs **Python ≥ 3.11** (old machine ran
      3.14.5). Recreate: `python3 -m venv .venv && .venv/bin/pip install -e .`
- [ ] **LM Studio + the model.** mu drives models via LM Studio's OpenAI API at
      `localhost:1234`. Install LM Studio, download **`qwen2.5-coder-7b-instruct` Q3_K_L**
      (the empirical 8 GB winner, 7/10), load it, and confirm it's served under the
      **bare id** `qwen2.5-coder-7b-instruct` (`curl localhost:1234/v1/models`).
      `MU_AGENT_MODEL` must match that id verbatim. Full rationale + the 8 GB GPU
      compute-buffer ceiling: `docs/quantization-and-the-stack.md`, `docs/MODELS.md`.
      Guardrails: disable LM Studio's auto-eviction / keep-loaded as the dotfiles do.
- [ ] **Toolchains** for the problems you'll run: `dotnet` (p4, p10), `clang`+`sdl2`
      (p3/p11/p12), node/npm (p9, p10 frontend), go, rust, etc. `mu dojo` only runs
      problems whose toolchains are installed.
- [ ] **`~/.mu/sessions/`** (≈121 MB, 2600+ run archives) does **not** travel and is
      **not needed** to resume — it's only the raw material for archive scans. If you
      want the historical diagnosis inputs, copy it separately (rsync); otherwise it
      rebuilds as you run.
- [ ] **`.mu/` runtime logs** (`collect*.log`, `agent.log`, nohup logs) are intentionally
      left behind — noise. Only the curated ablation artifacts + L0 boards travel (below).

Env knobs in play (all default-off; see the plan §4.1):
`MU_AGENT_MODEL=qwen2.5-coder-7b-instruct`, `MU_NUM_CTX=6000` (8192+ thrashes swap on
8 GB), `MU_ASPNET_ENTRYPOINT`, `MU_S2_TYPE_REFLEXES`, `MU_BUILD_ORDER`.

---

## `.mu/` artifacts carried on this branch (force-added past .gitignore)

Kept at their original `.mu/` paths so the orchestrators (`cd "$(dirname "$0")/.."`)
run unchanged:

- **Experiment infra** (prereg + orchestrator + analyzer + verdict per ablation):
  `abl_msb_*` (MSB1003 A/B — DONE, verdict present), `abl_s2b_*` (S2 re-eval — re-run),
  `abl_s2_*` (first S2 ablation, DROP→opt-in), `abl_bo_*` (build-order A/B), `abl_analyze.py`.
- **L0 boards** (`board_L0_*.json`): the reference boards per model. `board_L0_7b.json`
  is the live L0 reference (qwen-7b, 7/10, p10 bottleneck `backend_build` q̂=0.14).
- **Archive scans** (`round*_scan.md`): historical failure-mode analyses.

After the move, these stay gitignored on `main`, so they won't pollute normal work.

---

## Resume — quickest path

```sh
# 1. setup (see checklist above)
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ --ignore=tests/test_interaction_model.py -q   # expect 305 passed
# 2. start LM Studio, load qwen2.5-coder-7b-instruct Q3_K_L, verify:
curl -s localhost:1234/v1/models
# 3. A/B the entry-point lever (the top pending item) — author a prereg like
#    .mu/abl_msb_prereg.md, toggle MU_ASPNET_ENTRYPOINT on/off over p10 + p2/p4, N=15.
# 4. re-run the interrupted S2 re-eval:
nohup ./.mu/abl_s2b_run.sh > .mu/abl_s2b_nohup.log 2>&1 &
#    when done: cat .mu/abl_s2b_verdict.md
```

The authoritative running state is in agent memory (`project-p10-impl`) and the plan's
live checklist (`docs/plans/p10-minimization.md` §4.3, Step 0.5). This file is the
machine-move-specific overlay on top of those.
