#!/bin/zsh
# Honest-harness baseline: qwen3:8b, all 7 dojo problems (v0.6.0, 2026-05-22).
# v0.6.0 removed the Go plan-generator and all problem-specific sensors, so this
# run measures the model's real capability with only general language fixes left.
#
# Bias toward success over speed (per request): qwen3:8b is the most capable local
# model, MU_NUM_CTX=8192 gives it more context AND auto-scales timeouts 1.5x.
# Higher RAM pressure / swapping on the 8GB M2 is accepted.
#
# Execute from the repo root: dojo/claude-qwen3-8b-macos-m2-8gb-v0.6.0-2026-05-22/run-all.sh

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="claude-qwen3-8b-macos-m2-8gb-v0.6.0-2026-05-22"
RUN="$REPO/dojo/run.sh"

export MU_AGENT_BASE_MODEL=qwen3:8b
export MU_NUM_CTX=8192

cd "$REPO"
go build -o bin/mu ./cmd/mu

# Rebuild qwen3:mu from qwen3:8b at the new num_ctx (the existing one may be stale).
ollama rm qwen3:mu 2>/dev/null || true

$RUN $SESSION p1 p1-helloworld \
  "write a hello world program in C. Use clang to compile it and run it."

$RUN $SESSION p2 p2-sqlite \
  "write a Python todo list manager that stores todos in a SQLite database. Support add, list, and delete operations. Include a test file using pytest."

$RUN $SESSION p3 p3-sdl2 \
  "render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs."

$RUN $SESSION p4 p4-fibonacci \
  "write the fibonacci sequence using C#. Use the dotnet command to compile C#."

$RUN $SESSION p5 p5-go-gin \
  "write a Go HTTP server with a GET /ping endpoint that returns JSON {\"status\":\"ok\"}. Use the Gin framework. Include a Makefile."

$RUN $SESSION p6 p6-rust \
  "write a Rust program that prints Hello, world! Use Cargo."

$RUN $SESSION p7 p7-flask \
  "write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a 'task' field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest."
