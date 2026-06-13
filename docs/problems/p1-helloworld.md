# p1-helloworld — C hello world

**Toolchains:** clang · **Difficulty:** trivial

## Problem statement

> write a hello world program in C. Use clang to compile it and run it.

## What it does

The smallest possible end-to-end exercise: one `main.c` that prints
`Hello, World!`, plus a Makefile that compiles it with clang and runs the
binary. It validates the basic plan → write → build → run loop with no
test framework involved — if p1 fails, the harness itself (planner format,
Makefile generation, build gate) is usually what broke.

## Major challenges

- **Makefile escape artifacts** — recipe lines need a literal TAB; weak
  models emit literal `\n`/`\t` escapes or space-indented recipes
  (challenge [makefile-escape-artifacts](../challenges/makefile-escape-artifacts.md)).
- **Build-target inconsistency** — the plan names a binary the Makefile
  never builds, or vice versa (item 10).

## Related reflexes

- The Makefile reflex family: [`apply_makefile_reflexes`](../../src/mu/reflexes/makefile/apply_makefile_reflexes.py) (tab/indent/escape
  normalizers, orphan top-level commands, missing test target),
  [`fix_makefile_binary_name`](../../src/mu/reflexes/makefile/fix_makefile_binary_name.py) — aligns the recipe's output binary with the
  plan's test command.
- [`fix_literal_newlines`](../../src/mu/reflexes/core.py), [`fix_tool_call_artifacts`](../../src/mu/reflexes/core.py) — generic write-phase
  cleanup.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 12/12 |
| Median tokens / run | 4,570 prompt · 224 generated |
| Median repair iters | 0 |
| Heaviest phase | writer |

**Dominant errors this run:**
- None — passed every run.
