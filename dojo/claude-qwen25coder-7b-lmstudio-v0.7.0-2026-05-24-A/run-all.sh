#!/bin/zsh
# Clean full P1–P7 run, v0.7.0 (PyPA-packaged), qwen2.5-coder-7b-instruct.
# Runs inside an ISOLATED venv (/tmp/dojo-run-venv) so a problem's
# `pip install` can never mutate the host environment. Model is pinned
# (two models loaded → ensure-single would abort), so we skip it.
#
#   dojo/claude-qwen25coder-7b-lmstudio-v0.7.0-2026-05-24-A/run-all.sh

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SESSION="$(basename "$(dirname "$0")")"
DOJO="$REPO/dojo/$SESSION"
MU="/tmp/dojo-run-venv/bin/mu"
export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct

run() {
  local problem=$1 dir=$2 goal=$3
  echo "=== $problem Start: $(date +%s) ===" | tee "$DOJO/$problem.log"
  rm -rf "$DOJO/$dir"; mkdir -p "$DOJO/$dir"
  ( cd "$DOJO/$dir" && "$MU" agent "$goal" ) 2>&1 | tee -a "$DOJO/$problem.log"
  echo "=== $problem End: $(date +%s) (exit=${pipestatus[1]}) ===" | tee -a "$DOJO/$problem.log"
}

run p1 p1-helloworld \
  "write a hello world program in C. Use clang to compile it and run it."
run p2 p2-sqlite \
  "write a Python todo list manager that stores todos in a SQLite database. Support add, list, and delete operations. Include a test file using pytest."
run p3 p3-sdl2 \
  "render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs."
run p4 p4-fibonacci \
  "write the fibonacci sequence using C#. Use the dotnet command to compile C#."
run p5 p5-go-gin \
  "write a Go HTTP server with a GET /ping endpoint that returns JSON {\"status\":\"ok\"}. Use the Gin framework. Include a Makefile."
run p6 p6-rust \
  "write a Rust program that prints Hello, world! Use Cargo."
run p7 p7-flask \
  "write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a 'task' field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest."

echo "=== ALL DONE: $(date +%s) ===" | tee "$DOJO/run-complete.marker"
