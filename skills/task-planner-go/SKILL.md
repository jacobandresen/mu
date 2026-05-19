---
name: task-planner-go
description: Go-specific planning rules for PLAN.md. Loaded alongside task-planner when the goal involves Go, Gin, or golang.
---

# Go Planning Rules

- Lint tool: `go vet` (built-in, no extra install needed — list in ## Dependencies).
- The `go.sum` file is auto-generated; do **not** list it as a task in ## Files.

## External packages (gin, gorilla, etc.)

- List `go.mod` as the **first** file in ## Files. It sets the module path and Go version.
- The Makefile must run `go mod tidy` before building. Never silence it with `2>/dev/null || true` — a failed `go mod tidy` means the build will fail.
- In `go.mod`, always use the full module path: `require github.com/gin-gonic/gin v1.9.1`. Never write bare names like `gin v1.9.1`.

## Gin

- Assign the engine: `r := gin.Default()`, then call `r.GET(...)`, `r.Run()`.
- Never prefix it with a different name like `ingin`.
