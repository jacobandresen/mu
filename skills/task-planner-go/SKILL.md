---
name: task-planner-go
description: Go-specific planning rules. Loaded when goal involves Go, Gin, or golang.
---

- Lint: `go vet` (built-in)
- External packages: list `go.mod` first in ## Files. Makefile must run `go mod tidy` before building — never suppress errors.
- `go.mod` needs full paths: `require github.com/gin-gonic/gin v1.9.1`. Never write bare names.
- `go.sum` is auto-generated — do not list it as a task.
- Gin: `r := gin.Default()`, then `r.GET(...)`, `r.Run()`.
