---
name: repair-c
description: C/C++ repair diagnostics — map common compiler and make errors to targeted fixes.
---

- `No rule to make target 'X', needed by 'Y'` — the Makefile's `Y:` prerequisite names a file or target `X` that no rule produces. Change the prerequisite to the actual binary name (check the `-o NAME` flag in the compile recipe) or add a rule that builds `X`.
- `missing separator` — a recipe line starts with spaces instead of a TAB. Replace the leading spaces on that line with a single TAB character.
- `sdl2_line: No such file or directory` or SDL2 link errors — the binary target's recipe is running the binary instead of compiling it, or the SDL2 flags are missing. Fix the recipe to compile: `clang $(shell sdl2-config --cflags) -o sdl2_line main.c $(shell sdl2-config --libs)`.
- SDL2 `undefined symbol` or `library not found for -lSDL2` — add `$(shell sdl2-config --libs)` to the linker flags. On macOS with Homebrew, `sdl2-config` is at `/opt/homebrew/bin/sdl2-config`.
- `./binary: No such file or directory` — the compile step failed or the `-o` output name doesn't match what the run step expects. Check compiler output above this line and align the names.
- `undefined reference to '_main'` (or `undefined symbol _main`) — the source file has no `int main()` function. Add one.
- `implicit declaration of function 'X'` — include the header that declares `X` (e.g. `<stdio.h>` for `printf`, `<stdlib.h>` for `malloc`, `<string.h>` for `strlen`).
