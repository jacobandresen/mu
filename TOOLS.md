# Tools for the dojo challenges — a report

_A survey of external program-analysis and -transformation tools that could address the
failure classes in [challenges](docs/challenges/README.md), and an argument for when a
**tool** is the right instrument versus a hand-written **reflex**. mu is already a
tool-using agent (§5 lists what ships); this study maps which *further* tools to admit,
where they insert, and what each costs. Of the §6 proposals, **§6.1 (`dotnet new`
scaffold) and §6.3 (LSP client) are now shipped**; §6.2 (Roslyn-diagnostic coverage) and
§6.4 (libcst codemod) remain unbuilt. Everything marked ✓/◐ runs today._

> Scope note. By **reflex** we mean mu's own deterministic, post-write fixers
> (`src/mu/reflexes/`, chained by `run_reflexes`): mostly regular-expression or small
> AST edits that mu maintains in-tree. By **tool** we mean an external program —
> formatter, linter, type checker, compiler, AST-rewrite engine, scaffolder, or
> language server — invoked as a subprocess or service. Both are *deterministic*
> alternatives to prompting the model again; the question is which mechanism owns
> which class of error.

---

## 1. Background: where fixes enter the mu loop

mu drives a weak local model through a fixed pipeline (see [AGENTS.md](AGENTS.md) §4):

```
Planner ─▶ Plan lint ─▶ Writer ─▶ [REFLEXES] ─▶ Lint gate ─▶ Repair loop ─▶ Test gate
   │          (opt-in)     │           │             │            ▲   │           │
   │                       │           │             │            └───┘           │
 ground_plan          one file      deterministic  pyflakes    diagnose →     pytest/
 (normalizers)        per task      fixers          /autoflake  FOCUS hint    go test/…
```

Three observations frame the rest of this report:

1. **Reflexes occupy one slot** — immediately after each file is written, before the
   gates. They are cheap, synchronous, and dependency-free.
2. **The gates are already tools.** The lint gate shells out to `pyflakes`/`autoflake`;
   the test gate shells out to the language's compiler and test runner. mu is therefore
   *already* a tool-using agent; the open question is whether to admit *more* tools, and
   where.
3. **`diagnose` is an oracle reader.** It distils a tool's output (a compiler or test
   log) into a one-line FOCUS hint. Richer tools produce richer diagnostics, which makes
   the repair loop better-targeted even when no new fixer is added.

---

## 2. Reflexes versus tools: a trade-off analysis

The two mechanisms are not rivals so much as instruments suited to different error
classes. The automatic-program-repair literature frames the same tension as
*generate-and-validate* repair (cheap, pattern-driven, prone to overfitting) versus
*semantics-driven* repair (sound, heavier, tool-backed) — see
[Monperrus (2018)](https://arxiv.org/abs/1807.00515) and
[Le Goues et al. (2012)](https://doi.org/10.1109/TSE.2011.104).

| Dimension | Reflexes (mu's regex/AST fixers) | Tools (formatters, type checkers, AST engines, LSP) |
|---|---|---|
| Coverage | One concrete shape per fixer | A whole grammar-defined class at once |
| Grammar awareness | Usually regex — blind to scope/parse | Parse-accurate by construction |
| Dependencies | None (pure Python, runs on a Pi) | Toolchain / server install, version pinning |
| Latency | Microseconds, in-process | Process spawn or RPC; sometimes a warm server |
| Determinism | Total | High, but config/version-sensitive |
| Maintenance | Grows with every new shape; can misfire¹ | Upstream-maintained, battle-tested |
| Overfitting risk | High — easy to encode a test-specific hack | Low — a general tool can't target one dojo problem |
| Offline / air-gapped | Yes | Mostly yes; some need network for packages |
| Failure mode | Silent no-op or wrong edit | Crash, timeout, or environment error (cf. challenge [environment-hygiene](docs/challenges/environment-hygiene.md)) |

¹ The 2026-06-12 duplicate-import regression — a reflex re-adding a `from flask import …`
name it thought absent — is the canonical reflex hazard: a regex that is *almost* right.
A grammar-aware tool (an LSP "organize imports" action) cannot make that mistake.

The "Maintenance" and "Overfitting" rows have a live example in mu's own tree:
[`_csproj_content`](src/mu/plan.py) is a hand-rolled C# scaffolder. It must track every
SDK / TFM / package shape by hand, and — because it fires only when the model wrote *no*
csproj — it cannot prevent the model's own broken one (the dominant p10 failure, §6.1).
That is exactly the cost the table assigns reflexes, and the case for delegating it to
`dotnet new`.

**The verdict this report argues:** reflexes win the high-frequency, dependency-sensitive
fixes where a tool is disproportionate and the offline guarantee matters; tools win the
grammar-aware structural edits regex does brittlely, the *oracle* role (compilers and type
checkers feeding `diagnose`), and *scaffolding* — where the cheapest fix is to never emit
the broken structure. Both are bound by the honesty rule ([AGENTS.md](AGENTS.md) §0): a
fix, tool or reflex, must address a *general* class. A tool tuned to pass one dojo problem
measures the tool, not the agent.

---

## 3. Where tools and reflexes fit

The §1 pipeline has three insertion points for a deterministic fix, with different
economics — and this, not a flat "tools vs reflexes," is the design space:

- **Prevent — scaffolders, at plan time (earliest, cheapest).** An official template
  removes a class *by construction*; nothing downstream has to repair what was never
  emitted.
- **Transform — the contested post-write slot.** Reflexes and grammar-aware rewrite
  engines compete here for the same job; §2 is the argument over which owns which class.
- **Judge — oracle tools, at the gates.** Compilers, type checkers and linters don't edit
  code; they produce the diagnostics that `diagnose` distils into the FOCUS hint that
  targets the repair prompt.

Read the §4 catalogue against these three roles: the further left a tool acts, the more it
buys, because preventing a class is strictly cheaper than detecting then repairing it.

---

## 4. Catalogue of candidate tools

Grouped by role. "In mu?" marks what the harness already invokes (✓) or partially uses
(◐). Challenge links point to [`docs/challenges/`](docs/challenges/).

### 4.1 Scaffolders / project templates — *prevent the class*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `dotnet new xunit` / `webapi` | ✅ ([`scaffold.py`](src/mu/scaffold.py), `MU_SCAFFOLD`, opt-in) | [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md), [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |
| `create-vue` / `npm create vite` | ◐ (recipe present, online tier, deferred) | [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md), [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |
| `cargo new` | ◐ (recipe present; mu also regenerates a minimal `Cargo.toml`) | [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |

**mu already scaffolds C# — by hand, and now also via the official template.** `ground_plan`
writes a `.csproj` via [`_csproj_content`](src/mu/plan.py); behind `MU_SCAFFOLD` (opt-in,
default off), [`scaffold.py`](src/mu/scaffold.py) **delegates the hand-roll to `dotnet new`**:
it emits a correct `.csproj` with one entry point and matching test wiring, targeting the
installed SDK by construction (TFM + the net9+ `AllowMissingPrunePackageData` patch are
grounded in `dotnet --version`). Its edge is *ownership* — it takes the project file out of
the model's hands. **Measured (p10 A/B, N=15, [ablations.md](docs/ablations.md)):** the
NU1202/NETSDK1226 restore wall clears **12/15 → 0/15**, but backend_build stays 0/15 — the
weak model can't author a valid backend even scaffolded, so the lever ships **opt-in** pending
the entry-point/S2 re-test. This is the *minimization ladder* in [DOJO.md](DOJO.md): give the
scaffold, measure the logic — and the logic is now the binding constraint.

### 4.2 Transform tools — *grammar-aware fixers (the reflex substrate)*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `comby` (multi-language structural rewrite) | — | [csharp-generation-artifacts](docs/challenges/csharp-generation-artifacts.md), [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md), [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `libcst` (Python concrete-syntax tree) | — | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [missing-imports](docs/challenges/missing-imports.md), [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `ts-morph` / `jscodeshift` (TS/JS AST) | — | [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md), [missing-imports](docs/challenges/missing-imports.md) |
| `OpenRewrite` (JVM/recipe rewrites) | — | structural C#-adjacent rewrites (limited .NET support) |
| `black`, `gofmt`*, `rustfmt`, `prettier`, `dotnet format` | ◐ (`gofmt -e` used as a syntax oracle) | [makefile-escape-artifacts](docs/challenges/makefile-escape-artifacts.md)†, normalization that reduces lint noise |

*`gofmt -e` is already used by mu's `_syntax_check`. †Formatters require **parseable**
input; on a file with a syntax error they are a no-op, so they *cannot* fix the
malformed-generation classes — their value is normalization and preventing style drift,
which the report flags as a common misconception.

### 4.3 Oracle tools — *diagnostics that feed `diagnose` and the gates*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `pyflakes` | ✓ (lint gate) | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [missing-imports](docs/challenges/missing-imports.md) |
| `autoflake` | ✓ ([`py_autofix`](src/mu/reflexes/python/py_autofix.py)) | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md) |
| `ast.parse` (CPython) | ✓ (Python syntax check + rollback) | [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `ruff` (Rust-based Python linter/fixer) | — | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `mypy` / `pyright` | — | [missing-imports](docs/challenges/missing-imports.md), [incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md) (type-level) |
| `tsc --noEmit` | — | [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md), [missing-imports](docs/challenges/missing-imports.md) |
| `eslint` / `clippy` / `go vet` | — | [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md), [spurious-unused-imports](docs/challenges/spurious-unused-imports.md) |
| Roslyn analyzers (`dotnet build`) | ◐ (build gate runs; only `CS0017`/`CS8803` parsed into FOCUS so far — §6.2) | [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md), [csharp-generation-artifacts](docs/challenges/csharp-generation-artifacts.md) |
| Compilers / test runners (`clang`, `cargo`, `dotnet`, `go`, `node`) | ✓ (test gate) | all syntax/build classes (as ground truth) |

### 4.4 Language servers (LSP) — *a maintained reflex library*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `clangd`, `gopls`, `csharp-ls`, `pyright`, `rust-analyzer`, ts/Vue server | ✅ ([`lsp.py`](src/mu/lsp.py), `MU_LSP`; §6.3) | [missing-imports](docs/challenges/missing-imports.md), [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [csharp-generation-artifacts](docs/challenges/csharp-generation-artifacts.md), [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md) |

An LSP server exposes *code actions* ("add import", "remove unused", "organize imports",
"generate missing member") as `WorkspaceEdit`s over the Language Server Protocol. Many
mu reflexes are hand-rolled re-implementations of exactly these actions; the LSP client
obtains them grammar-accurately and upstream-maintained, at the cost of running a server
per language. **Shipped** — see §6.3 and [docs/lsp.md](docs/lsp.md).

### 4.5 Out of reach for any tool

[degenerate-repetition](docs/challenges/degenerate-repetition.md),
[stateful-backend-lifecycle](docs/challenges/stateful-backend-lifecycle.md), and
[incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md) are **model
ceiling**: they require *intent*, not transformation. No formatter, type checker, or AST
engine reconstructs what the program was meant to do. These remain prompt/skill/model
problems — consistent with the self-debugging results of
[Chen et al. (2023)](https://arxiv.org/abs/2304.05128), where the
model, not a tool, supplies the semantic fix.

---

## 5. Tools mu already employs

For the record, marked ✓/◐ above:

- **`pyflakes`** — the Python lint gate.
- **`autoflake`** — `py_autofix`, removes unused imports/variables.
- **`ast.parse`** — Python syntax check with edit rollback in the repair loop.
- **`gofmt -e`** — Go syntax oracle in `_syntax_check`.
- **`go mod tidy`** — [`apply_go_reflexes`](src/mu/reflexes/go/apply_go_reflexes.py), resolves Go module dependencies at the gate.
- **Compilers / test runners** — `clang`, `cargo`, `dotnet`, `go`, `node`, `pytest`,
  `jest`, `vitest` as the test gate; `sdl2-config` for p3.
- **`dotnet new`** — [`scaffold.py`](src/mu/scaffold.py) (`MU_SCAFFOLD`, opt-in); owns the C#
  project structure at ground time (§6.1).
- **Language servers** — [`lsp.py`](src/mu/lsp.py) (`MU_LSP`): clangd/gopls (fast, default)
  and csharp-ls/pyright/rust-analyzer/ts (slow, `MU_LSP=all`) for code-action repair (§6.3,
  [docs/lsp.md](docs/lsp.md)).

mu is thus already a tool-using agent in the ReAct sense
([Yao et al., 2023](https://arxiv.org/abs/2210.03629)); the proposals
below extend the *set* and the *insertion points*, they do not introduce the paradigm.

---

## 6. Candidate tools — proposals and what shipped

Ordered by the DOJO ranked backlog (p10 → p8 → p2). **§6.1 (scaffold) and §6.3 (LSP) are
now shipped** — their entries are condensed to the result + a pointer; **§6.2 and §6.4
remain proposals** and still name their **insertion point** (the real function it lands
in), the **change**, the **offline cost**, an **acceptance test on the `docs/ablations.md`
board**, and the **honest risk** — so a reader can start coding, not just nod.

### 6.1 — Own the C# project structure with `dotnet new` (p10) — ✅ SHIPPED

Built as [`scaffold.py`](src/mu/scaffold.py) (`MU_SCAFFOLD`, opt-in). The bet: instead of
peeling p10's `backend_build` cascade one error at a time, run `dotnet new webapi`+`xunit`
at ground time and *overwrite* the csproj + `Program.cs` so the model never authors the
`net5.0`+EF8 file that fails NuGet restore — **ownership**, not better XML. `dotnet new` is
fully offline (templates ship with the SDK); the restore that follows is the online step.
**Verdict (p10 A/B, N=15):** NU1202/NETSDK1226 restore wall clears **12/15 → 0/15**, but
backend_build stays 0/15 — the weak model can't author a valid backend even scaffolded, so
it ships opt-in. Full record + the prevent-vs-repair relation to `MU_TFM_GROUNDING`:
[docs/ablations.md](docs/ablations.md) (Scaffold row); the catalogue entry is §4.1.

### 6.2 — Type-checker / Roslyn diagnostics as a `diagnose` oracle (p2, p10; low-risk) — *unbuilt*

Split the two costs, because only one is cheap. **(a) Parsing is trivial and half-done:**
[`_RULES`](src/mu/diagnose.py) already grammars some Roslyn codes (`CS0017`, `CS8803`);
the cheap win is *extending* that coverage to the rest of the p10 cascade (`CS0246`,
`CS0101`, `CS0053`, `NU1202`) from the output the build gate **already produces** — *zero*
new dependency, just more `_rule(regex, render)` entries on the existing `F821` template.
No new fixer; just a sharper FOCUS hint at the exact symbol and line. **(b) Running a *new*
checker is the costly part:** `tsc --noEmit` and `mypy` run nothing today and need
`node_modules`/`@types` or a pip install — gate them on the toolchain being present, and
do them only after the free Roslyn-coverage win lands.

**Insertion:** grammars in `_RULES`; the invocation alongside the `gofmt -e`/`ast.parse`
oracles in [`_syntax_check`](src/mu/agent.py) or as a pre-test gate. **Acceptance:**
FOCUS-hit-rate on the run-7 archive traces (fraction of failed sessions that get a
specific, non-weak hint) before/after — measurable for the parsing half with *no* model
run. **Risk:** low — an oracle cannot misedit; the invocation half inherits
[environment-hygiene](docs/challenges/environment-hygiene.md).

### 6.3 — LSP code-action client (most general; replaces a reflex *family*) — ✅ SHIPPED

Built as [`src/mu/lsp.py`](src/mu/lsp.py) (`MU_LSP`): a stdio JSON-RPC client that requests
`textDocument/codeAction` + `source.organizeImports` per diagnostic and applies the returned
`WorkspaceEdit` (one action per round, re-diagnose), slotted into the post-write slot after
`run_reflexes`. Gating learned from the trials: `MU_LSP=1` runs only the fast proven servers
(clangd, gopls); `MU_LSP=all` opts into the slow ones (csharp-ls, pyright, rust-analyzer, ts).
**Finding:** a *selective* repair lever — clangd add-include and gopls organizeImports are
real wins, csharp-ls add-using fixes CS0246; net-negative with slow servers that return
nothing. Full client, trials, and per-challenge applicability: [docs/lsp.md](docs/lsp.md);
catalogue entry §4.4.

### 6.4 — Grammar-aware substrate for the *documented* misfire (libcst/comby) — *unbuilt*

Port the hazard the report already names, not an arbitrary fixer: footnote 1's
2026-06-12 duplicate-import regression — a regex re-adding a `from flask import …` it
wrongly thought absent — is the canonical reflex misfire. Re-express it as a `libcst`
codemod, which is **scope-aware**: it can *see* the existing import binding that the regex
misses. **Insertion:** keep the `run_reflexes` contract — the chain invokes each reflex as
`fn(target)` and detects edits by file hash, not by return value
([core.py](src/mu/reflexes/core.py)) — so an in-place libcst codemod fits it with zero
orchestration change.
**Offline tension:** `libcst` is a pip wheel (carries to the Pi); `comby` is a native
binary (an extra install) — prefer libcst for Python ports to keep the offline guarantee,
reserve comby for the multi-language cases libcst cannot reach. **Acceptance:** A/B the
ported fixer's misfire rate against the regex original; adopt only on a strict reduction.

---

Every proposal answers the same question the honesty rule poses of reflexes — *does it fix
a **general** class, and is the dependency justified by the breadth it buys?* — and one
more this report adds: *is it measured on the `docs/ablations.md` board, not asserted?*

---

## 7. Further reading

All references are online and linked. Verify a specific page before relying on it —
URLs were correct as of the 2026-01 knowledge cutoff.

**Automatic program repair (the reflex-vs-semantic-repair framing).**
- Monperrus, *Automatic Software Repair: a Bibliography*, ACM Computing Surveys 2018 —
  [arxiv.org/abs/1807.00515](https://arxiv.org/abs/1807.00515). The field's map;
  read on generate-and-validate vs semantics-driven repair.
- Le Goues et al., *GenProg: A Generic Method for Automatic Software Repair*, IEEE TSE
  2012 — [doi.org/10.1109/TSE.2011.104](https://doi.org/10.1109/TSE.2011.104). The
  canonical generate-and-validate system and its overfitting critique.

**LLM agents using tools and compilers (mu's paradigm).**
- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* —
  [arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629). Interleaving reasoning
  with tool calls.
- Schick et al., *Toolformer* —
  [arxiv.org/abs/2302.04761](https://arxiv.org/abs/2302.04761). Models learning when to
  call a tool.
- Yang et al., *SWE-agent: Agent–Computer Interfaces…* —
  [arxiv.org/abs/2405.15793](https://arxiv.org/abs/2405.15793). Why the *interface* to
  tools/gates dominates agent performance; directly relevant to mu's gates.
- Chen et al., *Teaching Large Language Models to Self-Debug* —
  [arxiv.org/abs/2304.05128](https://arxiv.org/abs/2304.05128). The compiler/test log as
  repair feedback (mu's `diagnose` is this idea, distilled).

**Structural transformation (the AST-rewrite substrate).**
- van Tonder & Le Goues, *Lightweight Multi-Language Syntax Transformation…*, PLDI 2019 —
  [doi.org/10.1145/3314221.3314589](https://doi.org/10.1145/3314221.3314589); tool at
  [comby.dev](https://comby.dev).
- [libcst](https://libcst.readthedocs.io) ·
  [jscodeshift](https://github.com/facebook/jscodeshift) ·
  [ts-morph](https://ts-morph.com) · [OpenRewrite](https://docs.openrewrite.org).

**Linters, formatters, type checkers (the oracle/transform tools).**
- [ruff](https://docs.astral.sh/ruff) · [pyflakes](https://github.com/PyCQA/pyflakes) ·
  [autoflake](https://github.com/PyCQA/autoflake) · [black](https://black.readthedocs.io) ·
  [mypy](https://mypy-lang.org) · [pyright](https://microsoft.github.io/pyright).
- [gofmt](https://pkg.go.dev/cmd/gofmt) · [go vet](https://pkg.go.dev/cmd/vet) ·
  [clippy](https://doc.rust-lang.org/clippy) ·
  [rustfmt](https://github.com/rust-lang/rustfmt).
- [eslint](https://eslint.org) · [prettier](https://prettier.io) ·
  [TypeScript](https://www.typescriptlang.org) ·
  [Roslyn analyzers](https://learn.microsoft.com/dotnet/fundamentals/code-analysis/overview).

**Protocols.**
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol) — the
  spec behind the §6.3 proposal; *code actions* and `WorkspaceEdit` are the relevant parts.
