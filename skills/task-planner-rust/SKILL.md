---
name: task-planner-rust
description: Rust/cargo-specific planning rules for PLAN.md. Loaded alongside task-planner when the goal involves Rust or Cargo.
---

# Rust / Cargo Planning Rules

Every cargo project requires a `Cargo.toml` file. Without it, `cargo build` and `cargo run` fail immediately. List `Cargo.toml` **first** in ## Files.

- Lint tool: `cargo clippy` (list in ## Dependencies).

## File layout

**Simple program**:
```
- [ ] Cargo.toml
- [ ] src/main.rs
```
Test Command: `cargo run`

## Rules

- Binary name in Test Command must match the `name` field in `[[bin]]`, or defaults to the package name in `[package]`. Use `cargo run` or `cargo build && ./target/debug/<name>`, not `cargo build --bin main` (the binary is not named `main` unless explicitly set).
- **Do not add a `[lib]` section** to Cargo.toml for a binary-only project. A `[lib]` entry requires `src/lib.rs` — if it does not exist, cargo fails with "can't find lib". Binary-only: just `[package]` + optional `[[bin]]`.
