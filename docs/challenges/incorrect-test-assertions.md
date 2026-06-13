# Incorrect test assertions

_‹ [All challenges](README.md)_

- **ID:** `incorrect-test-assertions`
- **Group:** Model ceiling
- **Open list:** [item 15](README.md#open)
- **Status:** not reflex-recoverable

## What it is

The test itself is wrong: wrong expected values, undeclared mock data, `KeyError` on a JSON response, an endpoint that isn't defined, bad CLI args. The code may be correct; the assertion is the defect.

## Problems affected

- [p9-vue-todo](../problems/p9-vue-todo.md) — `expected 'Todo ListAdd…' to contain <item>` — component renders heading+button, not the todo (run 7 ×6)
- [p8-node-todo](../problems/p8-node-todo.md) — mock returns the wrong shape

## Relevant reflexes & mechanisms

- `(none)` — test-design quality — diagnose surfaces the assertion but no reflex rewrites intent

## Residual / notes

Model quality; accept the variance rather than overfit a fixer to one assertion.
