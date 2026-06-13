# Syntax errors in test files

- **ID:** `test-file-syntax-errors`
- **Group:** Harness / environment
- **CHALLENGES.md:** item 17
- **Status:** JS + C# shapes covered by reflexes

## What it is

Syntax errors specifically in the generated test file: JS same-scope `const` re-declaration and `.[0]` member access; C# unmatched parens/semicolons and stuttered signature openers. Previously mislabeled 'Jest ESM' because the Jest banner shadowed the Babel SyntaxError detail.

## Problems affected

- [p8-node-todo](../problems/p8-node-todo.md) — same-scope `const todos = …` re-declared mid-block (10+ sessions)
- [p4-fibonacci](../problems/p4-fibonacci.md) — C# test-file syntax (stuttered openers)

## Relevant reflexes & mechanisms

- `fix_js_same_scope_redeclaration` — converts a re-declaration to assignment, promotes the first to `let`
- `fix_js_dot_bracket_access` — deletes the stray dot in `).[0]`
- `fix_csharp_consecutive_duplicate_signatures` — collapses stuttered C# test-method openers

## Residual / notes

diagnose now demotes banner-level hints so the specific Babel `SyntaxError` detail wins — the mislabel that hid this class is fixed.
