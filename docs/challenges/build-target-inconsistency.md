# Build-target inconsistency & misplaced files

_‹ [All challenges](README.md)_

- **ID:** `build-target-inconsistency`
- **Group:** Full-stack orchestration / multi-file
- **Open list:** [item 10](README.md#open)
- **Status:** mitigated by relocation + cleanup

## What it is

The plan names an entry-point/target the build file never defines (or vice versa), or the lean-retry writer writes a file to the wrong subdirectory.

## Problems affected

- [p1-helloworld](../problems/p1-helloworld.md) — binary name vs Makefile target
- [p4-fibonacci](../problems/p4-fibonacci.md) — entry point vs build target
- [p5-gin](../problems/p5-gin.md) — `go test` vs a named binary
- [p7-flask](../problems/p7-flask.md) — `make test` against a Makefile with no `test:` recipe
- [p14-fullstack-js-blog](../problems/p14-fullstack-js-blog.md) — files written to unexpected stage dirs
- [p15-dotnet-vue-blog](../problems/p15-dotnet-vue-blog.md) — files written to unexpected stage dirs


## Relevant reflexes & mechanisms

- [`fix_makefile_binary_name`](../../src/mu/reflexes/makefile/fix_makefile_binary_name.py) — aligns the Makefile's output binary with the test command
- `ground_plan` Level 2b/4a ([plan.py](../../src/mu/plan.py)) — synthesizes a Makefile when the plan uses `make` but ships none. The `cc -o` C template is now gated on the plan actually having C sources, so a Python project gets the venv Makefile (Level 4a) with a real `test: install` → `.venv/bin/pytest` target instead of a recipe-less `test:`.
- `_make_vacuous`/`_test_passed` ([agent.py](../../src/mu/agent.py)) — a make-only test command that prints `make: Nothing to be done` ran no tests; the gate now treats that as a failure, never a pass. `make && ./bin` is exempt (the binary's exit code is the real gate).
- `misplaced-file relocation` — moves a file the writer put in the wrong subdir to its planned path
- `stale-`.cs` cleanup` — removes orphaned duplicates before the build

## Residual / notes

Relocation tolerates filesystem races (a directory vanishing mid-walk no longer crashes the session — fixed 2026-06-12).

**False-pass class (fixed 2026-06-19).** p7-flask was scored `success` ~9× while running zero tests — a C `cc -o` Makefile gave `make test` no recipe, so it exited 0 doing nothing. The two mechanisms above (C-source-gated grounding + vacuous-make rejection) close it: a Flask API now must actually run pytest to pass.
