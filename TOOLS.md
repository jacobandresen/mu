# Tools for the dojo challenges — a report

_A survey of external program-analysis and program-transformation tools that could
address the failure classes in [CHALLENGES.md](CHALLENGES.md), and a discussion of
when a **tool** is the right instrument versus a hand-written **reflex**. This is a
design study — nothing here is implemented; the intent is to map the option space._

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
*semantics-driven* repair (sound, heavier, tool-backed) — see Monperrus (2018) and
Le Goues et al. (2012).

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

**The synthesis this report argues for:**

- **Reflexes win** for the high-frequency, low-complexity, dependency-sensitive fixes —
  artifact stripping, literal-newline repair, Makefile-tab normalization — where a tool
  would be disproportionate and the offline guarantee matters.
- **Tools win** for (a) *grammar-aware structural edits* that regex does brittlely
  (duplicate-class removal, import insertion, re-indentation), (b) the *oracle* role
  (compilers and type checkers as ground truth feeding `diagnose`), and (c)
  *scaffolding*, where the cheapest fix is to never generate the broken structure at all.
- **Both are bound by the honesty rule** ([AGENTS.md](AGENTS.md) §0): a tool, like a
  reflex, must address a *general* class. Shelling out to a formatter is honest; invoking
  a tool whose configuration is tuned to pass one dojo problem is not — and worse, it
  measures the tool, not the agent.

---

## 3. Where tools and reflexes fit — overview diagram

```
                         the mu autonomous loop
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                                                                            │
  │  PLAN TIME            WRITE TIME            GATE TIME            REPAIR     │
  │  ─────────            ──────────            ─────────           ──────     │
  │                                                                            │
  │  ┌─ scaffolders ─┐    model writes a file                                  │
  │  │ dotnet new    │          │                                              │
  │  │ create-vue    │          ▼                                              │
  │  │ cargo new     │   ┌──────────────┐                                      │
  │  │ (TOOLS)       │   │  REFLEXES     │  cheap, in-process, offline         │
  │  └───────┬───────┘   │  regex/AST    │  ── mu's home turf                  │
  │          │           └──────┬───────┘                                      │
  │          │                  │                                              │
  │          │           ┌──────▼────────┐   formatters / AST-rewrite engines  │
  │          │           │ TRANSFORM TOOLS│  black, gofmt, rustfmt, prettier,   │
  │          │           │ (grammar-aware)│  comby, libcst, ts-morph, OpenRewrite│
  │          │           └──────┬────────┘                                      │
  │          ▼                  ▼                                              │
  │   ground the         ┌───────────────┐   ORACLE TOOLS                       │
  │   workspace from      │  LINT / TYPE  │   pyflakes*, ruff, eslint, mypy,    │
  │   an official         │  / BUILD GATE │   tsc, clippy, Roslyn, compilers*   │
  │   template            └──────┬────────┘          │                          │
  │                              │                   ▼                          │
  │                              ▼            diagnose reads tool output →       │
  │                        ┌───────────┐     FOCUS hint leads the repair prompt  │
  │                        │ TEST GATE │*    pytest/jest/vitest/go test/dotnet   │
  │                        └───────────┘                                        │
  │                                                                            │
  │   * = already invoked by mu today (see §5)                                  │
  └──────────────────────────────────────────────────────────────────────────┘

  Legend:  REFLEXES = mu in-tree fixers (one shape each, no deps)
           TOOLS    = external programs: prevent (scaffold), transform (grammar-aware),
                      or judge (oracle). They widen coverage at the cost of dependencies.
```

The key spatial insight: **reflexes and transform-tools compete for the same slot**
(post-write), **oracle-tools augment the gates and `diagnose`**, and **scaffolders act
*earlier* than either** — they remove a class by construction rather than repairing it.

---

## 4. Catalogue of candidate tools

Grouped by role. "In mu?" marks what the harness already invokes (✓) or partially uses
(◐). Challenge links point to [`docs/challenges/`](docs/challenges/).

### 4.1 Scaffolders / project templates — *prevent the class*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `dotnet new xunit` / `webapi` | — | [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md), [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |
| `create-vue` / `npm create vite` | — | [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md), [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |
| `cargo new` | ◐ (mu regenerates a minimal `Cargo.toml`) | [build-target-inconsistency](docs/challenges/build-target-inconsistency.md) |

The official template emits a correct `.csproj`/`vite.config`/manifest with one entry
point and matching test wiring — exactly the structure p10 fails to assemble (CS0017,
MSB1003, NU1202). This is the single highest-leverage option for the one problem mu
cannot pass; it aligns with the *minimization ladder* already described in
[DOJO.md](DOJO.md) (give the scaffold, measure the logic).

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
| `autoflake` | ✓ (`py_autofix`) | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md) |
| `ast.parse` (CPython) | ✓ (Python syntax check + rollback) | [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `ruff` (Rust-based Python linter/fixer) | — | [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [generic-syntax-errors](docs/challenges/generic-syntax-errors.md) |
| `mypy` / `pyright` | — | [missing-imports](docs/challenges/missing-imports.md), [incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md) (type-level) |
| `tsc --noEmit` | — | [vue-vitest-jest-setup](docs/challenges/vue-vitest-jest-setup.md), [missing-imports](docs/challenges/missing-imports.md) |
| `eslint` / `clippy` / `go vet` | — | [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md), [spurious-unused-imports](docs/challenges/spurious-unused-imports.md) |
| Roslyn analyzers (`dotnet build`) | ◐ (build gate; diagnostics not yet parsed into FOCUS) | [csharp-aspnet-scaffolding](docs/challenges/csharp-aspnet-scaffolding.md), [csharp-generation-artifacts](docs/challenges/csharp-generation-artifacts.md) |
| Compilers / test runners (`clang`, `cargo`, `dotnet`, `go`, `node`) | ✓ (test gate) | all syntax/build classes (as ground truth) |

### 4.4 Language servers (LSP) — *a maintained reflex library*

| Tool | In mu? | Challenges it could address |
|---|---|---|
| `pyright`, `gopls`, `rust-analyzer`, `OmniSharp`, Vue/TS language server | — | [missing-imports](docs/challenges/missing-imports.md), [spurious-unused-imports](docs/challenges/spurious-unused-imports.md), [csharp-generation-artifacts](docs/challenges/csharp-generation-artifacts.md), [test-file-syntax-errors](docs/challenges/test-file-syntax-errors.md) |

An LSP server exposes *code actions* ("add import", "remove unused", "organize imports",
"generate missing member") as `WorkspaceEdit`s over the Language Server Protocol. Many
mu reflexes are hand-rolled re-implementations of exactly these actions; an LSP client
would obtain them grammar-accurately and upstream-maintained, at the cost of running a
server per language.

### 4.5 Out of reach for any tool

[degenerate-repetition](docs/challenges/degenerate-repetition.md),
[stateful-backend-lifecycle](docs/challenges/stateful-backend-lifecycle.md), and
[incorrect-test-assertions](docs/challenges/incorrect-test-assertions.md) are **model
ceiling**: they require *intent*, not transformation. No formatter, type checker, or AST
engine reconstructs what the program was meant to do. These remain prompt/skill/model
problems — consistent with the self-debugging results of Chen et al. (2023), where the
model, not a tool, supplies the semantic fix.

---

## 5. Tools mu already employs

For the record, marked ✓/◐ above:

- **`pyflakes`** — the Python lint gate.
- **`autoflake`** — `py_autofix`, removes unused imports/variables.
- **`ast.parse`** — Python syntax check with edit rollback in the repair loop.
- **`gofmt -e`** — Go syntax oracle in `_syntax_check`.
- **`go mod tidy`** — `apply_go_reflexes`, resolves Go module dependencies at the gate.
- **Compilers / test runners** — `clang`, `cargo`, `dotnet`, `go`, `node`, `pytest`,
  `jest`, `vitest` as the test gate; `sdl2-config` for p3.

mu is thus already a tool-using agent in the ReAct sense (Yao et al., 2023); the proposals
below extend the *set* and the *insertion points*, they do not introduce the paradigm.

---

## 6. Candidate tools to implement, and how

Ranked by leverage against the current open problems (see [TODO.md](TODO.md)).

1. **Template scaffolding at ground time (highest leverage for p10).**
   When `ground_plan` detects a `dotnet test` or Vue+Vitest goal, materialise the
   workspace from the official template (`dotnet new xunit`, `npm create vite`) and mark
   those files done, leaving the model to fill only the logic. *How:* extend the existing
   fixture/minimization mechanism in `dojo` — a template is a generated fixture. Directly
   attacks CS0017/MSB1003/NU1202 and the Vitest-config class by never emitting them.
   *Risk:* must stay general (scaffold *any* xunit/vite project, not p4/p10 specifically).

2. **Type-checker-as-oracle into `diagnose` (broad, low-risk).**
   Run `tsc --noEmit` / `mypy` / parse Roslyn diagnostics and feed the structured result
   into the FOCUS grammar. *How:* add grammars to `src/mu/diagnose.py` that read each
   checker's output; no new fixer, just a sharper hint. Improves
   [missing-imports](docs/challenges/missing-imports.md) and the C# classes where the
   compiler already knows the exact symbol and line.

3. **LSP code-action client (most general; replaces a reflex family).**
   Drive a headless language server, request `codeAction` for each diagnostic, apply the
   returned `WorkspaceEdit`. *How:* a thin LSP client in a new module; start with one
   server (`pyright` for "add/organize imports") and measure against the hand-rolled
   import reflexes before broadening. *Cost:* a server process per language and JSON-RPC
   plumbing — weigh against the offline/Pi constraint.

4. **AST-rewrite substrate for the riskiest reflexes (`comby`/`libcst`).**
   Re-express the structural fixers that regex does brittlely — duplicate-class removal,
   unindented-body repair — as grammar-aware rewrites. *How:* port one reflex (e.g.
   `fix_csharp_duplicate_classes`) to `comby` and A/B its precision; adopt only if it
   reduces misfires without new dependencies the target host can't carry.

Each proposal is gated by the same question the honesty rule poses of reflexes: *does it
fix a general class, and is the dependency justified by the breadth it buys?*

---

## 7. Further reading

**Automatic program repair (the reflex-vs-semantic-repair framing).**
- M. Monperrus, *Automatic Software Repair: a Bibliography*, ACM Computing Surveys 51(1),
  2018 — the standard map of the field; read §on generate-and-validate vs semantics-driven.
- C. Le Goues et al., *GenProg: A Generic Method for Automatic Software Repair*, IEEE TSE,
  2012 — the canonical generate-and-validate system and its overfitting critique.

**LLM agents using tools and compilers (mu's paradigm).**
- S. Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models*,
  arXiv:2210.03629 — interleaving reasoning with tool calls.
- T. Schick et al., *Toolformer*, arXiv:2302.04761 — models learning when to call a tool.
- J. Yang et al., *SWE-agent: Agent–Computer Interfaces…*, arXiv:2405.15793 — why the
  *interface* to tools/gates dominates agent performance; directly relevant to mu's gates.
- X. Chen et al., *Teaching Large Language Models to Self-Debug*, arXiv:2304.05128 — the
  compiler/test log as repair feedback (mu's `diagnose` is this idea, distilled).

**Structural transformation (the AST-rewrite substrate).**
- R. van Tonder & C. Le Goues, *Lightweight Multi-Language Syntax Transformation…*,
  PLDI 2019 — the theory behind `comby` (<https://comby.dev>).
- `libcst` <https://libcst.readthedocs.io>; `jscodeshift`
  <https://github.com/facebook/jscodeshift>; `ts-morph` <https://ts-morph.com>;
  `OpenRewrite` <https://docs.openrewrite.org>.

**Linters, formatters, type checkers (the oracle/transform tools).**
- `ruff` <https://docs.astral.sh/ruff>; `pyflakes`/`autoflake` (mu's current gate);
  `black` <https://black.readthedocs.io>; `mypy` <https://mypy-lang.org>;
  `pyright` <https://microsoft.github.io/pyright>.
- `gofmt` <https://pkg.go.dev/cmd/gofmt>; `go vet`; `clippy`
  <https://doc.rust-lang.org/clippy>; `rustfmt` <https://github.com/rust-lang/rustfmt>.
- `eslint` <https://eslint.org>; `prettier` <https://prettier.io>; TypeScript
  <https://www.typescriptlang.org>; Roslyn analyzers
  <https://learn.microsoft.com/dotnet/fundamentals/code-analysis/overview>.

**Protocols.**
- Language Server Protocol <https://microsoft.github.io/language-server-protocol> — the
  spec behind the §6.3 proposal; *code actions* and `WorkspaceEdit` are the relevant parts.

> Citations are to stable, canonical sources; arXiv identifiers are given where a paper is
> the primary reference. URLs were correct as of the 2026-01 knowledge cutoff — verify
> before relying on a specific page.
