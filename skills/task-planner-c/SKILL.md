---
name: task-planner-c
description: C/C++-specific planning rules for PLAN.md. Loaded alongside task-planner when the goal involves C, C++, SDL2, clang, or gcc.
---

# C / C++ Planning Rules

- Lint tool: `clang-tidy` (list in ## Dependencies).
- When `Makefile` is in ## Files, Test Command must be `make`. Otherwise inline: `gcc main.c -o main && ./main`.

## SDL2 / graphical programs

- SDL2 on macOS/homebrew: `sdl2-config --cflags` adds the SDL2 directory to the include path, so source files must use `#include <SDL.h>` (not `#include <SDL2/SDL.h>`).
- Interactive/graphical programs (SDL2, OpenGL, games — anything that opens a window) must **not** have unit test files. The only valid test is a compile smoke test.
- Test Command for graphical programs: `make` (compile only — **never** run the binary in a non-interactive test environment).
