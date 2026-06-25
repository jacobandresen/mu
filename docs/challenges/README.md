# Challenges — overview

One page per recurring failure class mu meets in the dojo. Each lists the problems that exhibit it and the reflexes/mechanisms that address it. **Status** is how well the harness handles it today.

The tables below are the human index (click through to the per-class pages for detail); the [Open section](#open) at the bottom is the machine knowledge base — the only part the learning loop writes (`mu reflect` after each round) and the planner reads back (next run). Keep the two from re-merging: humans read up here, the model reads down there.

_Status legend: **covered** = a reflex resolves it deterministically · **partial** = handled for common shapes, residue remains · **mitigated** = bounded by a mechanism, not eliminated · **model-ceiling** = beyond the weak model, no reflex can reach · **open** = no fixer yet._

## Group 1 — Degenerate / malformed generation

| Challenge | Status | Problems |
|---|---|---|
| [Generic syntax errors](generic-syntax-errors.md) | partial | p4, p5, p2 |
| [Unterminated string literals](unterminated-string-literals.md) | covered | p2 |
| [Spurious / unused imports](spurious-unused-imports.md) | covered | p6, p2 |
| [C# generation artifacts](csharp-generation-artifacts.md) | covered | p4, p10 |
| [Makefile escape artifacts](makefile-escape-artifacts.md) | covered | p1, p3, p7 |
| [Degenerate repetition](degenerate-repetition.md) | model-ceiling | p8, p10 |
| [C forward declarations / nested definitions](c-forward-declarations.md) | open | p1, p3 |

## Group 2 — Full-stack orchestration / multi-file

| Challenge | Status | Problems |
|---|---|---|
| [C# / ASP.NET scaffolding](csharp-aspnet-scaffolding.md) | partial — **p10 0-pass** | p4, p10 |
| [Vue / Vitest / Jest setup](vue-vitest-jest-setup.md) | covered | p8, p9, p10 |
| [Build-target inconsistency & misplaced files](build-target-inconsistency.md) | mitigated | p1, p5, p10 |
| [Repair-context budget](repair-context-budget.md) | mitigated | p8, p9, p10 |

## Group 3 — Model ceiling

| Challenge | Status | Problems |
|---|---|---|
| [Test isolation design](test-isolation-design.md) | partial (~50%) | p2, p7, p8 |
| [Stateful-backend lifecycle rewrites](stateful-backend-lifecycle.md) | model-ceiling | p7, p2 |
| [Missing imports](missing-imports.md) | partial | p7, p2, p10 |
| [Incorrect test assertions](incorrect-test-assertions.md) | model-ceiling | p9, p8 |

## Group 4 — Harness / environment

| Challenge | Status | Problems |
|---|---|---|
| [Environment hygiene](environment-hygiene.md) | covered | p2, p7 |
| [Syntax errors in test files](test-file-syntax-errors.md) | covered | p8, p4 |

## Open

_The machine knowledge base: lessons the reflect loop distils from failed runs and the planner reads back on the next goal — both ends of the loop touch only this section. Generic and cross-language by design; per-challenge error signatures and reflexes live in the tables and pages above._

1. **Test state leaks across runs**
  - Tests sharing mutable storage accumulate state between invocations; require setup/teardown that isolates state per test.

2. **Repair loop makes no forward progress**
  - Re-resolving the same dependency or re-applying the same reflex without changing the failing diagnostic stalls the run; each repair step must change the error or stop.

3. **Cross-file symbols and signatures must be shared, not redeclared**
  - A type, struct, constant, or function used in one unit but declared or defined in another the unit never includes yields unknown-type / undeclared-identifier / conflicting-types errors; put shared declarations in one header or module every consumer includes, and keep declaration and definition signatures identical.

4. **A symbol must be defined exactly once**
  - The same type or symbol defined in more than one compiled unit or namespace breaks the build; declare it once and share it, rather than duplicating the definition per file.

5. **Every used symbol must be provided at link time**
  - Undefined-reference errors mean a symbol is referenced but no compiled or linked unit supplies it; ensure all object files and libraries that define used symbols are in the link step.

