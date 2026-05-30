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
- **Binary target recipe must compile, not run.** When a target name matches the output binary (e.g. `myapp: main.c`), the recipe must be the compile command (`cc -o myapp main.c ...`), NOT a call to the binary (`myapp` or `./myapp`). Running the binary in its own build recipe causes infinite recursion or "No such file" errors.
- **Use `pkg-config` / `*-config` for library flags.** For C libraries that ship a config script (e.g. `sdl2-config`, `freetype-config`) or support `pkg-config`, always use `$(shell pkg-config --cflags --libs libname)` or `$(shell libname-config --cflags)` and `$(shell libname-config --libs)` — never hardcode `-I` include paths or `-l` link flags.
- **`test:` must run the test runner, not the application.** If the project uses pytest, the `test:` recipe must call `pytest` (or `.venv/bin/pytest`). Never make `test:` call `make run` or start the application server — that blocks forever.
