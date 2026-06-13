# C forward declarations / nested definitions

- **ID:** `c-forward-declarations`
- **Group:** Degenerate / malformed generation
- **CHALLENGES.md:** item 7
- **Status:** no scan reflex yet — diagnose names it

## What it is

C-specific: `call to undeclared function` (use before declaration) and `function definition is not allowed here` (a function nested inside another).

## Problems affected

- [p1-helloworld](../problems/p1-helloworld.md) — occasional use-before-declare
- [p3-sdl2](../problems/p3-sdl2.md) — helper defined inside main

## Relevant reflexes & mechanisms

- `(none yet)` — diagnose distils both messages into a FOCUS hint; no deterministic fixer

## Residual / notes

Open: a reflex could hoist a forward declaration or un-nest a definition, but neither is built. Currently relies on the model fixing it from the FOCUS hint.
