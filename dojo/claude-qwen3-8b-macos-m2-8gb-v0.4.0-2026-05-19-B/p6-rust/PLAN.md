## Files
- [x] Cargo.toml — Cargo manifest for Rust project
- [ ] src/main.rs — Rust source file implementing "Hello, world!"

## Test Command
cargo run

## Dependencies
- rustc (Rust compiler)
- cargo clippy (linting tool)
- rust-analyzer (for IDE integration)

```

## Repair History
- lint repair for src/main.rs — still failing. Error:
  ```
  error: invalid type: map, expected a sequence
   --> Cargo.toml:6:1
    |
  6 | [bin]
    | ^^^^^
  ```
