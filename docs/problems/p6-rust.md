# p6-rust — Rust Fibonacci CLI

**Toolchains:** cargo · **Difficulty:** moderate

## Problem statement

> write a Rust command-line program that prints the first 10 Fibonacci
> numbers. Use cargo to build and run.

## What it does

A cargo binary crate whose `main.rs` prints the first ten Fibonacci
numbers, with a `cargo test` unit test. Logic is trivial; the exercise is
really about `Cargo.toml` — a single invalid line in the manifest fails
the whole build before any Rust is compiled.

## Major challenges

- **Hallucinated manifest dependencies** — the model (especially in
  repair) adds `fibonacci = "0.1.1"`-style dependencies that are valid
  TOML but unresolvable, failing every build
  (challenge [spurious-unused-imports](../challenges/spurious-unused-imports.md)).
- **Unmatched braces / unused `use`** — generic Rust syntax issues
  (items 1, 3).

## Related reflexes

- `fix_rust_cargo_toml` — regenerates corrupted manifest structure;
  `fix_rust_cargo_bad_dependency` — strips unresolvable dependencies. The
  test-gate reapply hook force-runs this chain before every attempt, and
  the lint-repair hook resets `Cargo.toml` to a minimal grounded manifest.
- `apply_rust_source_reflexes`, `fix_rust_missing_trait_import`,
  `fix_rust_unbalanced_braces`.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 11/11 |
| Median tokens / run | 3,864 prompt · 254 generated |
| Median repair iters | 1 |
| Heaviest phase | repair |

**Dominant errors this run:**
- None — passed every run (median 1 repair iter, usually a Cargo.toml regen).
