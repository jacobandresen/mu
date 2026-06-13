# p5-gin — Go HTTP /ping server (Gin)

**Toolchains:** go · **Difficulty:** moderate

## Problem statement

> write a Go HTTP server with a GET /ping endpoint that returns JSON
> {"status":"ok"}. Use the Gin framework. Include a Makefile.

## What it does

A Gin router with one endpoint, a Go test that exercises it via
`httptest`, and a Makefile. The external dependency (Gin) makes module
resolution part of the exercise: `go.mod`/`go.sum` must exist and resolve
before anything compiles.

## Major challenges

- **Blocking test command** — plans write `./server` as the test command,
  which starts the HTTP server and hangs the gate forever; it must be
  `go test ./...` (challenge [build-target-inconsistency](../challenges/build-target-inconsistency.md)).
- **Module hygiene** — missing `go.mod`, unresolved Gin dependency.
- **Truncated generation** — a dangling `.Run()` with no receiver
  (`syntax error: unexpected .`), seen in the 2026-06-12 runs 3–4.

## Related reflexes

- Plan normalization rewrites the blocking `./binary` test command to a
  non-blocking check (`go test ./...`).
- `apply_go_reflexes` — runs `go mod tidy` to resolve module dependencies
  before each build attempt; `fix_go_trailing_dot` — removes dangling
  trailing `.` artifacts; `fix_go_missing_pkg_imports`,
  `fix_go_unused_imports`.

## Last measured

_Run 7 — 2026-06-12, 8 h collection, qwen2.5-coder-7b-instruct (ctx 6000)._

| Metric | Value |
|---|---|
| Pass rate | 11/12 |
| Median tokens / run | 6,897 prompt · 334 generated |
| Median repair iters | 0 |
| Heaviest phase | writer |

**Dominant errors this run:**
- `./main.go: syntax error: unexpected ., expected }` (×3) — a dangling `.Run()` with no receiver (truncated generation); `fix_go_trailing_dot` covers the simple case.
- Outcomes: final test gate failed (×1).
