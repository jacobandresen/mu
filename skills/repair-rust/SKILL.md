---
name: repair-rust
description: Rust repair diagnostics — map cargo/rustc error messages to targeted fixes.
---

- `format argument must be a string literal` — `println!(expr)` is wrong; the first argument must be a string literal. Use `println!("{}", expr)` or `println!("{expr}")`.
- `N positional arguments in format string, but there are M` — the number of `{}` placeholders must equal the number of arguments after the format string. Add or remove placeholders to match.
- `cannot find value 'X' in this scope` — `X` is not defined or not imported. Add `use crate::X;` or define the variable before use.
- `expected type 'T', found type 'U'` — add an explicit cast (e.g. `x as f64`) or change the variable's type to match.
- `unused variable` (warning as error) — prefix with `_` (e.g. `_x`) or remove it.
