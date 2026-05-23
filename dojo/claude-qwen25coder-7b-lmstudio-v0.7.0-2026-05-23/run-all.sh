#!/bin/zsh
# v0.7.0: first LM Studio backend run (Ollama removed).
# Model: Qwen2.5-Coder-7B-Instruct Q4_K_M via LM Studio on 192.168.0.162:1234.
# Honest harness: same general sensors as v0.6.x, no problem-specific fixes.
# MU_AGENT_MODEL left unset — auto-detected from first model in /v1/models.
#
# Execute from the repo root:
#   dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-23/run-all.sh

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-23"
RUN="$REPO/dojo/run.sh"

export MU_LMSTUDIO_HOST=http://192.168.0.162:1234
# MU_AGENT_MODEL intentionally unset: mu picks the first loaded model from /v1/models

cd "$REPO"
go build -o bin/mu ./cmd/mu

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
