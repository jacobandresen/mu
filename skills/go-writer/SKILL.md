---
name: go-writer
description: Go code-generation rules — HTTP testing, module setup, import discipline. Apply to any Go writing task.
---

- **Test HTTP servers with `httptest`, not `./main`.** A test command that runs `./main` starts a blocking server; if the port is in use it panics and cannot be repaired. Instead write a `_test.go` file that calls handlers via `httptest.NewRecorder()` and `http.NewRequest()`. The test command should be `go test ./...`.
- **Each file imports what it uses.** Imports are per-file. A `_test.go` file that uses `gin`, `json`, or any other package MUST import it explicitly — imports in `main.go` are NOT visible to `main_test.go`. Example: if the test calls `gin.Default()`, add `import "github.com/gin-gonic/gin"` to the test file.
- **Every declared variable must be used.** Go is a compile error for unused variables. Never declare a variable you don't reference.
- **Every import must be used.** Go is a compile error for unused imports. Only import packages you call.
- **`go.mod` module name must match the directory.** Run `go mod init <name>` where `<name>` is the directory name. The reflex handles this, but write it correctly from the start.
