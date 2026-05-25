#!/bin/zsh
# v0.7.0: Python rewrite, LM Studio backend, qwen2.5-coder-7b-instruct.
# Full LOCAL run to establish the v0.7.0 baseline (prior 05-23 run was
# network-interrupted on a remote host). Honest harness: general sensors only.
# Model auto-detected from the single loaded model (qwen2.5-coder-7b-instruct).
#
# Execute from the repo root:
#   dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-23-C/run-all.sh

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="$(basename "$(dirname "$0")")"
RUN="$REPO/dojo/run.sh"

cd "$REPO"

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
