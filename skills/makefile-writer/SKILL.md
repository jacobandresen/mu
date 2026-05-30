---
name: makefile-writer
description: Makefile correctness rules — newlines, tab indentation, target consistency, phony declarations. Apply to any task that includes a Makefile.
---

- **Real newlines only.** Never write `\n` escape sequences in Makefile content — they appear as literal characters and break parsing. Every target, recipe, and variable must be on its own line.
- **Targets at column 0.** Every target definition (`name:`) must start at the beginning of the line with no leading whitespace. A tab before `name:` makes it a shell command inside a recipe, not a target.
- **Tab-indent recipes.** Every recipe line must begin with a literal TAB, not spaces. The recipe goes on the line AFTER `target:`, never inline: `all: gcc main.c` treats `gcc main.c` as prerequisites, not a command.
- **Define every target the Test Command invokes.** If the test runs `make build && make test`, both `build:` and `test:` must exist in the Makefile.
- **Declare non-file targets `.PHONY`.** Targets that are not output files (`all`, `build`, `test`, `clean`, `run`, `install`) must appear in `.PHONY: all build test ...` at the top of the file, or Make will skip them if a file with the same name exists.
- **Run binaries with `./`.** To execute a compiled binary in a recipe, write `./binary`, not `run ./binary` or bare `binary`.
- **Binary target recipe must compile, not run.** When a target name matches the output binary (e.g. `sdl2_line: main.c`), the recipe must be the compile command (`clang -o sdl2_line main.c ...`), NOT a call to the binary (`sdl2_line` or `./sdl2_line`). Running the binary in its own build recipe causes infinite recursion or "No such file" errors.
- **SDL2 flags via sdl2-config.** For SDL2 projects, always use `$(shell sdl2-config --cflags)` and `$(shell sdl2-config --libs)` — never hardcode `-I` paths or `-lSDL2`. Example:
  ```
  CFLAGS=$(shell sdl2-config --cflags)
  LIBS=$(shell sdl2-config --libs)
  sdl2_line: main.c
  \tclang $(CFLAGS) -o sdl2_line main.c $(LIBS)
  ```
- **`test:` must run the test runner, not the application.** If the project uses pytest, the `test:` recipe must call `pytest` (or `.venv/bin/pytest`). Never make `test:` call `make run` or start the application server — that blocks forever.
