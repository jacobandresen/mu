# C forward declarations / nested definitions

_‹ [All challenges](README.md)_

- **ID:** `c-forward-declarations`
- **Group:** Degenerate / malformed generation
- **Open list:** [item 7](README.md#open)
- **Status:** no scan reflex yet — diagnose names it

## What it is

C-specific: `call to undeclared function` (use before declaration) and `function definition is not allowed here` (a function nested inside another).

## Problems affected

- [p1-helloworld](../problems/p1-helloworld.md) — occasional use-before-declare
- [p3-sdl2](../problems/p3-sdl2.md) — helper defined inside main

## Relevant reflexes & mechanisms

- `(none yet)` — diagnose distils both messages into a FOCUS hint; no deterministic fixer
- **LSP ([`lsp.py`](../../src/mu/lsp.py), `MU_LSP`)** — *diagnostic-only fit, not a fix.* `clangd`'s verified code action here is **add-include**, which solves the neighbouring missing-`#include` class but not these two: there is no reliable clangd quickfix that *hoists a forward declaration* or *un-nests a definition*. clangd would sharpen the diagnostic range, but the hoist/un-nest edit is unproven — don't expect LSP to close this one.

## Residual / notes

Open: a reflex could hoist a forward declaration or un-nest a definition, but neither is built. Currently relies on the model fixing it from the FOCUS hint. (LSP add-include covers missing `#include` but not the hoist/un-nest — see mechanisms above.)
