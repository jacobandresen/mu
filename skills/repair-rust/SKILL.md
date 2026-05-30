---
name: repair-rust
description: Rust repair diagnostics — map cargo/rustc error messages to targeted fixes.
---

- `not a function, use '!' to invoke the macro` — `println(...)` is missing the `!`. Change to `println!(...)`. Same applies to `print`, `eprintln`, `vec`, `assert`, `panic`, and any other Rust macro.
- `format argument must be a string literal` — `println!(expr)` is wrong; the first argument must be a string literal. Use `println!("{}", expr)` or `println!("{expr}")`.
- `N positional arguments in format string, but there are M` — the number of `{}` placeholders must equal the number of arguments after the format string. Add or remove placeholders to match.
- `cannot find value 'X' in this scope` — `X` is not defined or not imported. Add `use crate::X;` or define the variable before use.
- `expected type 'T', found type 'U'` — add an explicit cast (e.g. `x as f64`) or change the variable's type to match.
- `unused variable` (warning as error, `-D warnings`) — prefix the variable name with `_` (e.g. `let _x = ...`) or remove it entirely if not needed. Do NOT add `#[allow(unused_variables)]` — fix the root cause.
