# Challenges — overview

One page per recurring failure class mu meets in the dojo. Each lists the problems that exhibit it and the reflexes/mechanisms that address it. Grouped as in [lessons.md](lessons.md); **Status** is how well the harness handles it today.

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
