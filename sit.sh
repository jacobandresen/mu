#!/usr/bin/env bash

# sit.sh – Simple script to run mu dojo problems.
# Usage: sit.sh [problem-id]
#   [problem-id] Optional problem identifier (e.g., "p1-helloworld").
#                If omitted, all listed problems are run sequentially.
# Example:
#   ./sit.sh p1-helloworld
#   ./sit.sh   # runs all problems

set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [problem-id]"
  exit 1
fi

# Optional problem identifier; if empty, run all problems.
PROBLEM_ID="${1:-}"  # optional; if empty run all problems

# ---------------------------------------------------------------------------
# Function that returns the goal string for a given problem identifier.
# Returns success (0) if the problem is known, otherwise returns non‑zero.
# ---------------------------------------------------------------------------
get_goal() {
  case "$1" in
    p1-helloworld)
      echo "write a hello world program in C. Use clang to compile it and run it."
      ;;
    p2-sqlite)
      echo "write a Python todo list manager that stores todos in a SQLite database. Support add, list, and delete operations. Include a test file using pytest."
      ;;
    p3-sdl2)
      echo "render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs."
      ;;
    p4-fibonacci)
      echo "write the fibonacci sequence using C#. Use the dotnet command to compile C#."
      ;;
    p5-gin)
      echo "write a Go HTTP server with a GET /ping endpoint that returns JSON {\"status\":\"ok\"}. Use the Gin framework. Include a Makefile."
      ;;
    p6-rust)
      echo "write a Rust command-line program that prints the first 10 Fibonacci numbers. Use cargo to build and run."
      ;;
    p7-flask)
      echo "write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a \"task\" field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest."
      ;;
    *)
      return 1
      ;;
  esac
}

# List of all known problem identifiers (used when no specific problem is given).
PROBLEMS=(p1-helloworld p2-sqlite p3-sdl2 p4-fibonacci p5-gin p6-rust p7-flask)

# Determine which mu binary to invoke (prefer local bin/mu if available).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${SCRIPT_DIR}/bin/mu" ]]; then
  MU_CMD="${SCRIPT_DIR}/bin/mu"
else
  MU_CMD="mu"
fi

run_problem() {
  local folder="$1"
  local goal="$2"
  local workdir="./dojo/${folder}"
  mkdir -p "${workdir}"
  pushd "${workdir}" > /dev/null
  echo "Running problem '${folder}'"
  "${MU_CMD}" agent "${goal}" --dir .
  popd > /dev/null
}

if [[ -n "${PROBLEM_ID}" ]]; then
  # Run a single specified problem.
  if ! GOAL=$(get_goal "${PROBLEM_ID}"); then
    echo "Unknown problem ID: ${PROBLEM_ID}" >&2
    exit 1
  fi
  run_problem "${PROBLEM_ID}" "${GOAL}"
else
  # Run all problems defined in the PROBLEMS array.
  for folder in "${PROBLEMS[@]}"; do
    GOAL=$(get_goal "${folder}")
    run_problem "${folder}" "${GOAL}"
  done
fi

# End of script

# Commit any Git changes (if any) after all runs have completed.
# This ensures that we only clean the dojo directory after the changes
# have been recorded in version control.
if git rev-parse --git-dir > /dev/null 2>&1; then
  # Check for uncommitted changes (including staged and unstaged).
  if ! git diff-index --quiet HEAD --; then
    echo "Committing changes before cleaning..."
    git add .
    # Use a generic commit message; the user can amend later if needed.
    MU_VER=$(awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py)
    git commit -m "Mu dojo run: record changes (mu version $MU_VER)"
  else
    echo "No changes to commit."
  fi
else
  echo "Not a git repository; skipping commit step."
fi

# Clean the dojo directory after the run.
# This ensures a fresh state for subsequent runs. It removes all files
# and subdirectories inside the dojo folder while preserving the folder
# itself. The command is safe even if the folder is empty.

echo "Cleaning dojo directory..."
# Use find to delete everything inside dojo, ignoring the dojo directory itself.
if [ -d "dojo" ]; then
  find dojo -mindepth 1 -exec rm -rf {} + || true
fi
# Clean the dojo directory after the run.
# This ensures a fresh state for subsequent runs. It removes all files
# and subdirectories inside the dojo folder while preserving the folder
# itself. The command is safe even if the folder is empty.

echo "Cleaning dojo directory..."
# Use find to delete everything inside dojo, ignoring the dojo directory itself.
if [ -d "dojo" ]; then
  find dojo -mindepth 1 -exec rm -rf {} + || true
fi
