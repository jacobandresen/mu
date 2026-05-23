#!/bin/zsh
# v0.6.1: same honest harness as v0.6.0, PLUS the iterative repair loop
# (agent.Session.RepairLoop). Identical model settings to v0.6.0 (qwen3:8b,
# num_ctx=8192) so the delta vs the v0.6.0 baseline isolates the repair loop.
#
# Expectation: P3/P4/P6/P7 (which failed in v0.6.0 with "Repair: max turns
# reached" and zero server drops) should recover. P2/P5 server drops are a
# separate problem addressed in a later run.
#
# Execute from the repo root: dojo/claude-qwen3-8b-macos-m2-8gb-v0.6.1-2026-05-23/run-all.sh

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="claude-qwen3-8b-macos-m2-8gb-v0.6.1-2026-05-23"
RUN="$REPO/dojo/run.sh"

export MU_AGENT_BASE_MODEL=qwen3:8b
export MU_NUM_CTX=8192

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
