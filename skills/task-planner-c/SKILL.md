---
name: task-planner-c
description: C/C++-specific planning rules. Loaded when goal involves C, C++, SDL2, clang, or gcc.
---

- Lint: `clang-tidy`
- With Makefile: Test Command is `make`. Without: `gcc main.c -o main && ./main`
- SDL2 (macOS): use `#include <SDL.h>` — `sdl2-config --cflags` puts SDL2 on the include path.
- Graphical programs (SDL2, OpenGL, anything opening a window): no unit tests. Test Command is `make` (compile only — never run the binary).
