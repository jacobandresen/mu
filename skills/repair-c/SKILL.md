---
name: repair-c
description: C/C++ repair diagnostics — map common compiler and make errors to targeted fixes.
---

- `No rule to make target 'X', needed by 'Y'` — the Makefile's `Y:` prerequisite names a file or target `X` that no rule produces. Change the prerequisite to the actual binary name (check the `-o NAME` flag in the compile recipe) or add a rule that builds `X`.
- `No rule to make target 'X', needed by 'all'` (where X is the binary name, not a source file) — the Makefile declares `all: X` but has no rule that builds `X`. Add a compile rule: `X: main.c\n\tcc -o X main.c $(CFLAGS) $(LDFLAGS)`. Use the actual source file names from the project.
- `target pattern contains no '%'` — Make is reading a line as a static pattern rule (`targets: pattern: prereqs`) because there are two colons. Either the inline recipe was put on the target line (`hello_world: main.c: cc -o hello_world main.c`) or the same name appears twice (`hello_world: hello_world: main.c`). Fix: split into a proper rule with a tab-indented recipe on the next line, e.g. `hello_world: main.c\n\tcc -o hello_world main.c`.
- `missing separator` — a recipe line starts with spaces instead of a TAB. Replace the leading spaces on that line with a single TAB character.
- `BINARY: No such file or directory` where BINARY matches a Makefile target — the target's recipe is running the binary instead of compiling it. Fix: the `BINARY:` target recipe must contain the compile command (`cc -o BINARY main.c ...`), not a call to the binary.
- `library not found for -lXXX` or `undefined symbol` for a library function — the library flags are missing from the link step. Use `$(shell pkg-config --libs libname)` or `$(shell libname-config --libs)` to supply the correct flags. Do NOT prefix `$(shell sdl2-config --libs)` with a bare `-L` — the output already contains `-L/path -lSDL2`; adding `-L` before it produces `-L -L/path` which breaks the linker.
- `./binary: No such file or directory` — the compile step failed or the `-o` output name doesn't match what the run step expects. Check compiler output above this line and align the names.
- `undefined reference to '_main'` (or `undefined symbol _main`) — the source file has no `int main()` function. Add one.
- `implicit declaration of function 'X'` — include the header that declares `X` (e.g. `<stdio.h>` for `printf`, `<stdlib.h>` for `malloc`, `<string.h>` for `strlen`).
