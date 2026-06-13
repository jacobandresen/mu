# p3-sdl2 — Draw a line via SDL2

**Toolchains:** clang, sdl2 · **Difficulty:** moderate

## Problem statement

> render a line on screen via SDL2. Use sdl2-config in the Makefile to set
> up SDL2 libs.

## What it does

A small C program that initializes SDL2, renders a line, and exits — the
graphics analogue of p1. The interesting part is the build: the Makefile
must use `sdl2-config --cflags --libs` to locate headers and libraries,
and the "test" is that the program compiles and runs headlessly without
hanging.

## Major challenges

- **Build flags** — models hardcode `-lSDL2` or invent include paths
  instead of using `sdl2-config`, which only works by accident on some
  machines ([lessons](../challenges/lessons.md) items 5, 10).
- **C declaration discipline** — `call to undeclared function`, nested
  function definitions (item 7).
- **Blocking run** — an SDL event loop that waits for input hangs the test
  gate; the program must exit on its own.

## Related reflexes

- The Makefile reflex family (`apply_makefile_reflexes`,
  `fix_makefile_binary_name`) keeps the `sdl2-config` invocation in a
  valid recipe.
- Plan normalization rewrites blocking `./binary` test commands into
  non-blocking checks.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 12/12 |
| Median tokens / run | 8,177 prompt · 575 generated |
| Median repair iters | 0 |
| Heaviest phase | writer |

**Dominant errors this run:**
- None — passed every run.
