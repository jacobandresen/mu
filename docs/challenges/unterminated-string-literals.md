# Unterminated string literals

- **ID:** `unterminated-string-literals`
- **Group:** Degenerate / malformed generation
- **CHALLENGES.md:** item 2
- **Status:** covered by reflexes; still model-frequent

## What it is

The model leaves a string open: Python triple-quoted SQL strings never closed, Go strings missing a closing quote.

## Problems affected

- [p2-sqlite](../problems/p2-sqlite.md) — multi-line SQL in `execute('''…`

## Relevant reflexes & mechanisms

- `fix_multiline_single_quote` — converts a multi-line single-quoted SQL string to a triple-quoted one
- `fix_missing_close_paren` — closes a missing `)` after a triple-quoted `execute(` call

## Residual / notes

Lint-driven; the diagnose FOCUS hint names the unterminated-literal line.
