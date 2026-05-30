---
name: repair-go
description: Go repair diagnostics — map go build/test errors to targeted fixes.
---

- `address already in use :PORT` — the test runs `./main` which starts a blocking server; it cannot be tested this way. Edit `main.go` to read the port from an environment variable (`os.Getenv("PORT")`) with a fallback, so a test can pass `PORT=0` and avoid collisions. Better: move handler logic to a testable function and call it from `main`.
- `undefined: X` — `X` is not imported or not exported. If `X` is in another package, add the import; if it is unexported (lowercase), either export it (uppercase) or access it differently.
- `X declared and not used` — Go requires every declared variable to be used. Remove it or replace with `_`.
- `cannot use X (type T) as type U` — add an explicit conversion: `U(X)`.
- `no test files` — Go only runs tests from files ending in `_test.go` with functions `func TestXxx(t *testing.T)`. If no such file exists, no tests run and the goal is unverified.
