## Files
- [x] src/main.rs — Rust program that prints "Hello, world!" using Cargo

## Test Command
cargo run

## Dependencies
rustc, cargo

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  error: invalid type: map, expected a sequence
   --> Cargo.toml:5:1
    |
  5 | [bin]
    | ^^^^^
  ```
- test repair attempt 2 — still failing. Error:
  ```
  error: invalid type: map, expected a sequence
   --> Cargo.toml:7:1
    |
  7 | [bin]
    | ^^^^^
  ```
- test repair attempt 1 — still failing. Error:
  ```
  error: could not find `Cargo.toml` in `/Users/jacob/Projects/mu/dojo/claude-qwen3-8b-macos-m2-8gb-v0.6.0-2026-05-22/p6-rust` or any parent directory
  ```
