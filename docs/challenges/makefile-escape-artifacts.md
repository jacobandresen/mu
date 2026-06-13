# Makefile escape artifacts

_‹ [All challenges](README.md)_

- **ID:** `makefile-escape-artifacts`
- **Group:** Degenerate / malformed generation
- **Open list:** [item 5](README.md#open)
- **Status:** covered by the makefile reflex family

## What it is

Recipe lines need a literal TAB; the lean retry path emits literal `\n`, `\t`, `\@` or space-indents recipes, which `make` rejects.

## Problems affected

- [p1-helloworld](../problems/p1-helloworld.md) — build recipe indentation
- [p3-sdl2](../problems/p3-sdl2.md) — `sdl2-config` recipe
- [p7-flask](../problems/p7-flask.md) — install/test recipes

## Relevant reflexes & mechanisms

- `apply_makefile_reflexes` — tab/indent/escape normalizers, orphan top-level commands, missing test target
- `fix_makefile_literal_tab_escape` — real TAB for a literal `\t`
- `fix_makefile_binary_name` — aligns the recipe's output binary with the plan's test command

## Residual / notes

Among the highest-firing reflex families — a firing means a Makefile was repaired, not that the session failed.
