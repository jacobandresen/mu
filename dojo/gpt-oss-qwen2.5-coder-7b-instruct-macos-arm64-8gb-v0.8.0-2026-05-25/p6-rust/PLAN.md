## Summary
Implement a Rust program that prints "Hello, world!" using Cargo. Build with Cargo and verify by running the executable.

## Files
- [ ] main.rs — Rust source code
- [ ] Cargo.toml — Cargo configuration

## Test Command
cargo run

## Dependencies
rustc, cargo

## Challenges
- lint repair needed for main.rs
  ```
  error: could not find `Cargo.toml` in `/Users/jacob/Projects/mu/dojo/gpt-oss-qwen2.5-coder-7b-instruct-macos-arm64-8gb-v0.8.0-2026-05-25/p6-rust` or any parent directory
  ```
- near-empty file written for main.rs (44 bytes)

## Repair History
- lint repair for main.rs — still failing. Error:
  ```
  Checking hello_world v0.1.0 (/Users/jacob/Projects/mu/dojo/gpt-oss-qwen2.5-coder-7b-instruct-macos-arm64-8gb-v0.8.0-2026-05-25/p6-rust)
  error: unexpected closing delimiter: `}`
   --> src/main.rs:5:1
    |
  1 | fn main() {
  ```
