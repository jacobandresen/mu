## Files
- [x] src/main.rs — Rust program that prints the first 10 Fibonacci numbers

## Test Command
cargo build --bin main && cargo run --bin main

## Dependencies
- rustc (>=1.60)
- cargo
- cargo clippy

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  error: invalid type: map, expected a sequence
   --> Cargo.toml:6:1
    |
  6 | [bin]
    | ^^^^^
  ```
- test repair attempt 1 — still failing. Error:
  ```
  error: could not find `Cargo.toml` in `/Users/jacob/Projects/mu/dojo/claude-qwen3-8b-macos-m2-8gb-v0.3.0-2026-05-18/p6-rust` or any parent directory
  ```
