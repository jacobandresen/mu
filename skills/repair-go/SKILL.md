---
name: repair-go
description: Go repair diagnostics — map go build/test errors to targeted fixes.
---

- `address already in use :PORT` — the test runs `./main` which starts a blocking server; it cannot be tested this way. Edit `main.go` to read the port from an environment variable (`os.Getenv("PORT")`) with a fallback, so a test can pass `PORT=0` and avoid collisions. Better: move handler logic to a testable function and call it from `main`.
- `undefined: X` — `X` is not imported or not exported. If `X` is in another package, add the import to THIS file; if it is unexported (lowercase), either export it (uppercase) or access it differently. Common case in test files: `gin`, `json`, or a framework type used in the test but not imported in the test file — each file needs its own import block.
- `X declared and not used` — Go requires every declared variable to be used. Remove it or replace with `_`.
- `cannot use X (type T) as type U` — add an explicit conversion: `U(X)`.
- `no test files` — Go only runs tests from files ending in `_test.go` with functions `func TestXxx(t *testing.T)`. If no such file exists, no tests run and the goal is unverified.
- `X (value of type func(...) ...) is not used` — you referenced a method value `obj.Method` without calling it. This is a statement that evaluates to a function but throws it away. Add the call: `obj.Method(args)`. Example: `router.Run` → `router.Run(":8080")`. Check all lines in the function for bare method references and add the missing call.
