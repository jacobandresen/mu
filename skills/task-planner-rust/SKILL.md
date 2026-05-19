---
name: task-planner-rust
description: Rust/cargo-specific planning rules. Loaded when goal involves Rust or Cargo.
---

- List `Cargo.toml` FIRST in ## Files — without it, cargo fails.
- Simple: `Cargo.toml` then `src/main.rs`. Test: `cargo run`
- Binary name = package name in `[package]`. Use `cargo run`, not `cargo build --bin main`.
- Do NOT add `[lib]` to Cargo.toml for binary-only projects — it requires `src/lib.rs` to exist.
- Lint: `cargo clippy`
