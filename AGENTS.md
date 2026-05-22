# AGENTS.md

Operating guide for AI agents (and humans) working on the **mu** codebase.
mu is a local AI coding toolkit: `mu agent "<goal>"` drives an autonomous
plan → write → verify loop on top of a local Ollama model.

This file is the source of truth for *how to work on mu*. If it conflicts with
older docs (e.g. `HARNESS_ENGINEERING.md`, `README.md`), this file wins; those
predate the 2026-05-22 "honest harness" refactor and are partly historical.

---

## 0. Prime directive: keep the dojo honest

The `dojo/` benchmark runs 7 fixed problems (helloworld C, SQLite Python, SDL2 C,
fibonacci C#, Go/Gin, Rust, Flask). Its purpose is to measure the **agent
harness's real capability** at driving a small local model — not to score points.

**Do not optimize the harness against the specific dojo problems.** Concretely:

- **No hardcoded languages.** Don't add a `switch lang { case "python": ... }`
  that bakes in the test languages, and never key behavior off the dojo goals.
  The LLM planner produces `PLAN.md`; the model decides file names and structure.
  (The old Go plan-generator and its problem-name filename list were removed for
  exactly this reason — v0.6.0.)
- **No problem-specific sensors.** A deterministic fixer is only allowed if it
  corrects a *general class* of model error in a language or build system. If the
  bug only shows up because one dojo problem happens to exercise it, it's overfit.
- **When a dojo problem fails, the honest fix is a general one:** a better model
  choice, a better *generic* prompt rule, or a general mechanism — never a
  band-aid that pattern-matches that one problem's output.

Why this matters: a sensor that swaps `SDL_DestroySurface`→`SDL_FreeSurface` or
injects a `pip install` step measures *the harness author's knowledge of the
test*, not the agent. That inflates scores and hides the real capability gap.

---

## 1. The sensor test

`internal/sensors/` holds deterministic, model-free fixers applied after a file
is written. Before adding or keeping one, apply this test:

> **Would I write this exact fix for any program in this language/build system,
> independent of the dojo? If the answer is "no, only because problem X needs
> it," the sensor is overfit — don't add it.**

**Allowed (general language-class fixes) — these currently exist:**

| Area | Sensor | Why it's general |
|------|--------|------------------|
| Makefile | `FixMakefileSpaceIndent` | Make *requires* tab-indented recipes — true for every Makefile |
| Makefile | `FixOrphanTopLevelCommands`, `FixNoTargets`, `FixInlineRecipe`, `FixDuplicateVar` | General Makefile syntax repair |
| Python | `FixMultilineSingleQuote`, `FixMissingCloseParen` | General Python syntax errors |
| Python | `FixTestImportModule` | Test imports a module name that isn't on disk — general |
| Python | `RuffAutoFix` | Runs `ruff --fix`; a general linter |

**Removed (problem-specific) — do NOT reintroduce in any form:**
SDL2 include/API fixers, `FixMakefileSDL2`, `FixMakefilePipInstall`, all
`FixCsproj*`, all Cargo/`go.mod`/`FixGoMakefile`/`FixGoLiteralNewlines` fixers,
`FixDotnetTestCommand`, `FixGraphicalTestCommand`, `FixNoMakefileTestCommand`,
`FixPythonMakefileTest`, `FixPytestPath`. These each encoded one dojo problem.
`CHALLENGES.md` keeps them as a *historical* record ("Fix landed" = "was tried").

---

## 2. Prefer generic instructions over sensors

When the model makes a mistake that *is* general to a language, the right fix is
usually a **prompt rule in `buildAutonomousSystem` (the writer system prompt)**,
not a post-hoc sensor. A prompt rule teaches the model to get it right the first
time and generalizes to programs the dojo never tests.

**Rule for prompt additions: same honesty test as sensors.** An instruction is
acceptable only if it's true for *all* programs in that language/build system.
Never write "if the goal mentions SDL2…" into a prompt.

**Candidate generic instructions** (proposed; apply *after* the v0.6.0 baseline
so we measure the raw model first — see §4):

- *Makefiles:* "Indent every recipe line with a TAB, never spaces. Every Makefile
  must define a default target. Put each recipe command on its own tab-indented
  line, not on the target line."
- *Python testability:* "Write modules that are safe to `import`: initialize any
  required state (DB schema, etc.) at module load, not only under
  `if __name__ == '__main__'`, so tests can import and use the module directly."
- *Test files:* "Import from the real module/file you created and call its exact
  public names." (A weaker form already exists in `buildWritePrompt`.)
- *Python strings:* "Multi-line string literals must use triple quotes."

**Do NOT** turn these into prompt rules — they are environment/problem-specific
and belong nowhere: SDL3-vs-SDL2 API choice, `.csproj` TargetFramework matching
the installed SDK, pinning hallucinated dependency versions, injecting specific
pip packages. If the model gets these wrong, that's a real capability signal.

---

## 2.5 The v0.3 lesson: a general iterative loop beats sensors

The highest dojo score ever recorded is **v0.3 (2026-05-17): 6/7** — higher than
every sensor-laden version since (v0.4–v0.6 peaked at 5/7). v0.3 had only a handful
of sensors. What it had instead was **`pi` as a general, iterative agent** driving
the writer and especially the repair phase.

The decisive difference is in the logs:

```
v0.3 repair:  "Repair: tests pass after 68s — stopping pi."
```

v0.3's repair was a full agent session that could **run the test command, read the
failure, edit, re-run, and iterate until green** — mu just polled for a passing test
and stopped the agent. The current `runRepair` does the opposite: Bash is withheld
(`agent.RepairToolDefs`), it gets ~4 turns, makes one blind edit, and **cannot
observe whether its fix worked**. `finalTestGate` retries it twice with no feedback
loop inside.

**Lesson — and the priority generic improvement:** the path back to 6/7+ is a real
iterative repair loop with test feedback (edit → run test → feed result back → repeat
until green or budget exhausted), not more sensors. The original reason Bash was
withheld ("the model wastes turns re-running tests instead of fixing") solved the
wrong problem — running the test *is* how an agent knows what to fix. Prefer a
harness-driven loop (harness runs the test after each edit and feeds the output back)
so test execution stays deterministic while the model still gets to iterate.

This is the clearest evidence for AGENTS.md's thesis: **invest in general agent
capability, not problem-specific patches.**

---

## 3. Architecture (where things live)

`mu agent` is a deterministic control plane composing specialized model sessions:

- **Planner** (`runPlanner` / `runCombinedPlanner`) → LLM produces `PLAN.md`
  (`## Files`, `## Test Command`, `## Dependencies`). Always an LLM call now.
- **Writer** (`runWriterWithSession`) → one file per task; tools restricted to
  Write/Edit (`agent.WriterToolDefs`).
- **Sensors** (`internal/sensors/`) → general deterministic fixes post-write.
- **Lint gate → Repair → Test gate → Final test gate** → `runRepair` uses
  Write/Edit/Read only (no Bash) so the model fixes code instead of re-running tests.
- **Plan hygiene** (`internal/plan/`) → general normalizers only
  (`NormalizeEmbeddedFiles`, `NormalizeTestCommand`, `DropRuntimeArtifacts`,
  `CheckGoalAlignment`). Language/problem-specific plan rewrites were removed.
- **Skills** (`skills/`) → embedded via `//go:embed`; only the language-agnostic
  `task-planner` skill remains.
- `PLAN.md` is externalized task state — it survives context resets; the model
  writes it, the harness reads/normalizes it.

Prompts: `buildAutonomousSystem` (writer), `buildPlannerSystem`/`buildPlannerPrompt`,
`buildWritePrompt`, and the repair `fixRules` — all in `internal/subcommands/agent.go`.

---

## 4. Dojo workflow & run config

- Each run lives in `dojo/<model>-<host>-<version>-<date>[-suffix]/run-all.sh`.
- Scores are tracked in `RUNS.md` (timing per problem; `X` = fail).
- **Bias success over speed** (8GB M2): use the most capable local model
  (currently `qwen3:8b`), accept longer runtimes and RAM swapping. Set
  `MU_NUM_CTX=8192` — it gives more context *and* auto-scales planner/writer
  timeouts 1.5× (`detectComplexity`).
- The agent model is a `:mu` variant built from the base (`qwen3:8b` → `qwen3:mu`)
  with `num_ctx` baked in at creation. To change context size,
  `ollama rm qwen3:mu` first so it rebuilds.
- Server drops (`prompt=0 gen=0`) under memory pressure are expected;
  `chatOrRetry` reloads and retries.
- After removing a sensor or plan rule, scores are *expected* to drop — that's the
  honest number, not a regression to paper over.

---

## 5. Build / test / commit

```
make build            # go build -o bin/mu ./cmd/mu
go test ./...         # unit tests
go vet ./...
```

- Keep commits focused and atomic (separate refactor from data/runs).
- Don't add documentation files unless asked.
- Don't reintroduce a `pi`/node/npm dependency — mu drives Ollama natively now.
  (The README still lists `pi`; it is stale.)

---

## 6. Known open issues (general, not yet fixed)

- **Repair-prompt file confusion:** the repair agent sometimes writes one file's
  content into another (e.g. Makefile text into `main.c`). This is a *general*
  prompt-clarity problem worth fixing generically — not per-problem.
