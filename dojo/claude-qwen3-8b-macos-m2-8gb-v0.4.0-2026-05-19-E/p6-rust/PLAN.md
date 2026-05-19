## Files
- [x] Cargo.toml
- [ ] src/main.rs

## Test Command
cargo run

## Dependencies
Rust → cargo clippy

## Repair History
- lint repair for src/main.rs — still failing. Error:
  ```
  Updating crates.io index
  error: failed to select a version for the requirement `clippy = "^0.1.0"`
  candidate versions found which didn't match: 0.0.302, 0.0.301, 0.0.300, ...
  location searched: crates.io index
  required by package `hello-world v0.1.0 (/Users/jacob/Projects/mu/dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-E/p6-rust)`
  ```
