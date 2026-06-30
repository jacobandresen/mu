# Generic syntax errors

_‹ [All challenges](README.md)_

- **ID:** `generic-syntax-errors`
- **Group:** Degenerate / malformed generation
- **Open list:** [item 1](README.md#open)
- **Status:** partial — per-language reflexes cover common shapes; residue is model quality

## What it is

Plain syntax mistakes a weak model makes across languages: Python indentation/colons, C#/Rust unmatched braces, Go composite-literal missing commas, JS syntax, missing semicolons. Each language has reflexes for its recurring shapes; what's left is one-off model error.

## Problems affected

- [p5-gin](../problems/p5-gin.md) — `./main.go: syntax error: unexpected ., expected }` — a dangling `.Run()` (run 7 ×3)
- [p2-sqlite](../problems/p2-sqlite.md) — Python def/class body written at the parent's column (`expected an indented block`)
- [p4-fibonacci](../problems/p4-fibonacci.md) — `CS1519: Invalid token` in C# member declarations
- [p15-dotnet-vue-blog](../problems/p15-dotnet-vue-blog.md) — `CS1519: Invalid token` in C# member declarations

## Relevant reflexes & mechanisms

- [`fix_python_unindented_body`](../../src/mu/reflexes/python/fix_python_unindented_body.py) — indents a def/class body left at column 0 (ast-rollback)
- [`fix_python_method_indent`](../../src/mu/reflexes/python/fix_python_method_indent.py) — re-indents a `def` after a class-level decorator
- [`fix_go_trailing_dot`](../../src/mu/reflexes/go/fix_go_trailing_dot.py) — removes a dangling trailing `.`
- [`fix_rust_unbalanced_braces`](../../src/mu/reflexes/rust/fix_rust_unbalanced_braces.py) — rebalances Rust braces
- [`fix_csharp_missing_braces`](../../src/mu/reflexes/csharp/fix_csharp_missing_braces.py) — closes unbalanced C# braces

## Residual / notes

Most residual cases are model quality — no reflex can anticipate every malformed token. The lint/test gate plus FOCUS hints route the model to the offending line.
