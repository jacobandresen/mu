# Dojo

The dojo stress-tests **mu** by driving a guest model through a fixed problem set
(P1–P7) and recording where the autonomous loop breaks. Problem prompts live in
[PRACTICE.md](docs/PRACTICE.md); model selection and tuning in [MODELS.md](docs/MODELS.md)
and [TUNING.md](docs/TUNING.md); the design rationale in
[HARNESS_ENGINEERING.md](docs/HARNESS_ENGINEERING.md).

Current backend: **LM Studio** (OpenAI-compatible API), model
**qwen2.5-coder-7b-instruct** Q4_K_M. Updated 2026-05-24 (v0.7.0).

> **Environment prerequisite.** The pytest problems (P2, P7) require a pytest
> compatible with the host Python. On **Python 3.14**, pytest < 8 crashes inside
> its own assertion rewriter (`AttributeError: module 'ast' has no attribute
> 'Str'`) before collecting any test — see [C0](#c0). Use `pytest >= 8`
> (verified on 9.0.3). Run the dojo in an **isolated virtualenv**: a problem's
> `make test` does `pip install -r requirements.txt`, which otherwise mutates the
> shared environment (also [C0](#c0)).

> **Honest-harness principle.** Fixes must be *language-class generic*, never
> pattern-matched to one dojo problem. A sensor that rewrites "SDL3→SDL2" or
> injects a known `.csproj` measures the harness author's knowledge of the test,
> not the agent. The Go-era sensor zoo (v0.3–v0.6) was deleted for this reason.
> Every fix below uses a real oracle — the compiler, the package manager, the
> SDK — to name the problem, so it generalises beyond P1–P7.

---

## Last 3 runs

`✓` pass · `X` fail · `—` not run. Per-problem result for the 7-problem set.

| Run | Score | P1 hello | P2 sqlite | P3 sdl2 | P4 C#/fib | P5 go/gin | P6 rust | P7 flask |
|-----|-------|----------|-----------|---------|-----------|-----------|---------|----------|
| [C](../dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-23-C/) — first true local baseline | **3/7** | ✓ | X 400 | ✓ | X 400 | X 400 | ✓ | X 400 |
| [05-24-A](../dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-24-A/) — clean full run (pytest fix + Go sensor + packaged) | **4/7** | ✓ | X* iso | ✓ | X conv | ✓ | ✓ | X conv |
| [05-24-B](../dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-24-B/) — A/B: `python-env` skill ON (P2/P7 only) | — | — | X lint | — | — | — | — | X conv |

- **C** is the first uninterrupted *local* run (the earlier remote run was
  network-cut). Every failure died on the **HTTP 400** transport bug (C1), which
  masked each problem's real cause. (Follow-up runs **D**/**E**/**F**, since
  deleted, cleared C1, added `ground_plan`, and wired `go mod tidy` — their
  lessons are folded into C1/C2/C3.)
- **05-24-A** is the current clean baseline: genuine **4/7** (P1, P3, P5, P6).
  **P5 newly green** — the [C3](#c3) Go unused-import sensor + `go mod tidy`
  cleared its compile failures. `X*` on P2 marks a **false positive** the run
  exposed ([C8](#c8)): the planner dropped the `## Test Command`, the gate was
  *skipped*, and "Goal complete" was reported though the tests fail on shared-DB
  state. Now fixed by a gate-time `pytest` default. P4/P7 are genuine
  model-convergence fails (C4/C5-class).
- **05-24-B** isolates the **`python-env` skill** (now loaded for Python tasks —
  see [C0](#c0)/Skills). It reaches the writer+repair prompt (logged "Loaded
  python-env skill") but did **not** flip P2/P7: the 7B model still wrote
  shared-state tests and stale code. The feature works; the ceiling is model
  convergence, not missing guidance.

Net: pass/fail score still **3/7** (P1, P3, P6), but the failure *modes* are now
honest. The dominant blocker was environmental ([C0](#c0)), not the agent; the
surviving gates are genuine model-convergence (C4, C5, and P2's test isolation).

---

## Challenges

Each entry: **Symptom** (exact error) · **Cause** · **Impact** (problem / stage) ·
**Codebase pointer** (where the fix lives or should land) · **Related work**
(one-line industry approach) · **Status**.

<a id="c0"></a>
### C0 — Toolchain / dependency version skew · LANDED (env) + open (isolation)

The single highest-leverage finding. Two distinct skews, both masquerading as
agent failures across **P2 and P7**:

**(a) pytest too old for the host Python.**
- **Symptom:** `AttributeError: module 'ast' has no attribute 'Str'` raised inside
  `_pytest/assertion/rewrite.py` — *before any test is collected*. Every pytest
  invocation fails identically.
- **Cause:** `ast.Str` was removed in Python 3.12+; pytest 6.2.4 (2021) still
  calls it in its assertion rewriter. Host here is Python **3.14.5**.
- **Impact:** P2 and P7 were **categorically unwinnable** — no model output can
  fix a crash inside pytest itself. The repair loop then flailed on unfixable
  errors (see C6).
- **Codebase pointer:** none — environment. The harness can only *surface* it;
  the fix is `pip install -U pytest`. Verified: pytest 6.2.4 → **9.0.3** turns P2
  from "crash" into **2/3 passing** and P7 into a real (fixable) Flask error.
- **Related work:** `tox` / `nox` / lockfiles pin the test toolchain to the
  interpreter — the standard guard against exactly this skew.
- **Status:** fixed in the venv (pytest 9.0.3).

**(b) model-pinned deps mutate the shared venv.**
- **Symptom:** `ImportError: cannot import name 'url_quote' from 'werkzeug.urls'`.
- **Cause:** P7's plan emits a `requirements.txt` with stale pins
  (`Flask==2.0.1`, `SQLAlchemy==1.4.25`); the Makefile's `make test` runs
  `pip install -r requirements.txt` into the **active (shared)** environment,
  downgrading Flask against the modern Werkzeug already installed → import break.
  It both fails the test *and corrupts the host venv for other projects*.
- **Impact:** P7 — and any pytest+pip problem — is non-deterministic and
  environment-destructive.
- **Codebase pointer:** test execution `src/mu/agent.py:449` `_final_test_gate`
  → `_run_cmd`. Fix direction (see [Where to push next](#where-to-push-next)):
  run each problem's test command inside a throwaway `python -m venv`, so
  `pip install` is sandboxed and version skew can't reach the host.
- **Related work:** per-project virtualenvs / ephemeral CI containers — the
  universal Python isolation pattern; also captured as a repo skill
  (`src/mu/skills/python-env/SKILL.md`).
- **Status:** open (isolation). Documented as the top harness fix.

### C1 — Tool-call `arguments` re-sent as object → HTTP 400 · LANDED

- **Symptom:** `400 Bad Request` from LM Studio on every turn after the first
  tool call; multi-turn repair silently dies.
- **Cause:** the assistant message was replayed into history with `arguments`
  parsed back into a dict. The OpenAI tool schema requires `arguments` to be a
  JSON *string*.
- **Impact:** all of P2/P4/P5/P7 in run C — masked their real failures.
- **Codebase pointer:** `src/mu/client.py:202` — `arguments` is now stored as
  `json.dumps(parsed)`; `tools.dispatch` parses it back at call time.
- **Related work:** the OpenAI Chat Completions spec mandates string `arguments`;
  SDKs (openai-python, Vercel AI SDK) serialise tool args before echoing them.
- **Status:** fixed; 400s went many → 0 across C→D.

### C2 — Ungrounded plan: C# never built / Go dep never resolved · LANDED

- **Symptom (C#):** `MSB4025` "project file could not be loaded" — the plan ran
  `dotnet run --project Fibonacci.cs` with no `.csproj`.
  **Symptom (Go):** `no required module provides package github.com/gin-gonic/gin`.
- **Cause:** the only plan validator was a bag-of-words goal-keyword check; it
  cannot catch a structurally invalid build command or a missing project/module
  file. The toolchain, not the model, is the authority on project shape and deps.
- **Impact:** P4 never compiled; P5 never linked Gin.
- **Codebase pointer:** `src/mu/plan.py:281` `ground_plan()` writes a canonical
  SDK `.csproj` (TargetFramework grounded in `dotnet --version`,
  `plan.py:236`) and canonicalises the `dotnet` command. Go deps:
  `src/mu/sensors.py` `apply_go_sensors()` runs `go mod init` + `go mod tidy`,
  wired at `agent.py:236` (write) and `agent.py:413` (each build attempt).
- **Related work:** "verification before execution" / plan-grounding — the agent
  validates artifacts against tools before acting (cf. Devstral/OpenHands scaffolds).
- **Status:** fixed. P4 now compiles; P5 now resolves Gin (revealing C3).

### C3 — Go rejects unused imports · LANDED (this iteration)

- **Symptom:** `./main.go:4:2: "encoding/json" imported and not used` (also `os`)
  — a hard compile error in run F.
- **Cause:** small models emit speculative imports they never reference. Go
  treats any unused import as a fatal error, so the build never starts.
- **Impact:** P5 — build fails after Gin resolves; the repair loop edited
  `main.go` five times without converging.
- **Codebase pointer:** `src/mu/sensors.py` `fix_go_unused_imports()` — runs
  `go build ./...`, parses `"<path>" imported and not used`, removes exactly the
  named import lines, loops (removal can surface the next). Called from
  `apply_go_sensors()`, so it runs in both the write and repair phases.
- **Related work:** `goimports` (golang.org/x/tools) auto-strips unused and adds
  missing imports; we use the compiler as oracle to avoid a tool dependency.
- **Status:** fixed. **P5 now passes** (clean run 05-24-A) — the sensor + `go
  mod tidy` carry it end-to-end. Does **not** fix unused *locals* (C4).

### C4 — Go server never started (missing `r.Run`) · OPEN (model convergence)

- **Symptom:** `declared and not used: port`; even with imports clean the program
  defines a route but never serves.
- **Cause:** the model wrote `port := ":8080"` and the `GET /ping` handler but
  omitted `r.Run(port)` — a logic gap, not a syntax error. No generic tool can
  invent the missing call without becoming problem-specific.
- **Impact:** P5 — server binary is incomplete; tests can't hit `/ping`.
- **Codebase pointer:** repair loop `src/mu/agent.py:400` `_run_test_repair_loop`
  / `_REPAIR_LOOP_RULES` (`agent.py:36`). Improvement: feed the *compiler's*
  "declared and not used" line into the repair prompt as an explicit hint (as
  `_run_repair_lint` already does for Python SQL errors, `agent.py:419`), and/or
  upgrade the guest model — Qwen2.5-Coder-7B under-converges on multi-step logic.
- **Related work:** iterative test-feedback repair (SWE-bench agents); a stronger
  agentic model (Devstral, 53.6% SWE-bench) is the lever, not a harness hack.
- **Status:** open — deliberately not papered over per the honest-harness rule.

### C5 — C# emits two `Main` methods · OPEN (model convergence)

- **Symptom:** duplicate-entry-point build error — qwen wrote a `Main` in both
  `Fibonacci.cs` and `Program.cs`, and in repair authored a second malformed
  `.csproj`.
- **Cause:** the model doesn't track the single-entry-point constraint across
  files; repair compounds it by rewriting project scaffolding.
- **Impact:** P4 — compiles individually but the project has two entry points.
- **Codebase pointer:** repair loop `src/mu/agent.py:400`. `ground_plan`
  (`plan.py:281`) already pins one canonical `.csproj`; the open gap is constraining
  the repair model from authoring competing entry points / project files.
- **Related work:** same as C4 — a more capable agentic model converges here.
- **Status:** open — model-convergence, not a harness bug.

<a id="c6"></a>
### C6 — "Repair loop wanders to phantom paths" · FALSIFIED (was a symptom of C0)

- **Original hypothesis:** repair edits files under a non-existent `tests/`
  directory (P2, run D) or rewrites `requirements.txt` 6× (P7, run D) instead of
  the real source — so the repair prompt must need tighter file scoping.
- **What the live 05-24 run showed:** with a **fixable** error in view (pytest
  fixed, C0), the repair loop targeted the **correct** files every time —
  P2 edited `todo_manager.py` ×6; P7 edited `app.py` ×3 + `tests/test_app.py` ×2.
  The earlier "wandering" only happened when the model was handed an *unfixable*
  error (the C0 pytest crash) and thrashed because no edit could ever pass.
- **Conclusion:** not a repair-scoping defect. The existing rule "only modify
  files that already exist" (`_REPAIR_LOOP_RULES`, `agent.py:39`) is sufficient
  once the error is real. **No harness change made** — fixing C0 dissolved it.
- **Residual (real) gap:** repair edits a *plausible but wrong* file when the bug
  is elsewhere — P2 edited the (correct) impl 6× while the actual bug was test
  isolation in `test_todo_manager.py`. That is model convergence (C4-class), not
  file targeting.
- **Status:** closed as mis-diagnosis; tracked under C0 (root cause) and C4
  (convergence on the remaining bug).

### C7 — Writer stalls: prose instead of tool call / near-empty file · MITIGATED

- **Symptom:** `Writer produced near-empty X (N bytes)`; or many tokens of prose
  with no Write/Edit call.
- **Cause:** small models narrate the change instead of calling the tool, or stop
  after a few tokens on trivial files.
- **Impact:** intermittent across problems; costs a retry cycle.
- **Codebase pointer:** retry-with-thinking + fenced-code-block extraction in
  `src/mu/session.py`.
- **Related work:** constrained / structured tool-calling and grammar-enforced
  decoding (BFCL-style) reduce prose-instead-of-call failures.
- **Status:** mitigated by retry + code-block extraction; ~1–2× per run.

<a id="c8"></a>
### C8 — Test gate skipped when planner omits `## Test Command` · LANDED

- **Symptom:** agent logs `No '## Test Command' in PLAN.md — skipping final test
  gate`, then `Goal complete` — a **false positive**. P2 in run 05-24-A reported
  success while its tests actually fail 2/4 (shared-DB isolation).
- **Cause:** the planner sometimes drops the `## Test Command` section (often
  when it wraps the whole plan in ``` code fences). With no command, the final
  gate had nothing to run and returned success without testing.
- **Impact:** any problem whose plan loses the test command silently "passes"
  untested — the harness over-reports its own score.
- **Codebase pointer:** `src/mu/agent.py:456` `_final_test_gate` — now, when the
  command is missing **but the plan has test files**, it defaults to
  `pytest <testfiles>`; it only skips when there is genuinely nothing to verify.
- **Related work:** CI "no tests ran" / `--strict` flags treat an empty test
  collection as failure, not success — same honesty principle.
- **Status:** fixed. General (any test-file presence triggers it), not
  problem-specific.

---

<a id="where-to-push-next"></a>
## Where to push next

1. **Isolate each problem's test run in a throwaway venv** (C0b) — now the
   highest-leverage *harness* fix. `python -m venv .venv && .venv/bin/pip install
   -r requirements.txt && .venv/bin/pytest`, scoped per problem in
   `_final_test_gate` (`agent.py:449`). Makes pytest+pip problems deterministic
   and stops `make test` from corrupting the host environment. Minimal, generic,
   no model dependency.
2. **C4/C5/P2-isolation** are model-convergence walls: the cleanest path is a
   stronger agentic guest model (Devstral on 16 GB — see [MODELS.md](docs/MODELS.md)),
   not more sensors. A 7B model won't reliably add a `tmp_path` fixture or track a
   single-entry-point constraint across files.
3. Keep feeding compiler/oracle output verbatim into repair prompts — the honest,
   generic signal that has already cleared C1–C3. Extending it to surface the
   *test file* (not just impl) as an edit candidate would address P2's residual.
4. **C6 is closed** (mis-diagnosed). Don't add repair-scoping machinery; the
   real wins were environmental (C0) and are model-bound (C4/C5).
