#!/usr/bin/env bash

# sit.sh – Simple script to run mu dojo problems.
# Usage: sit.sh [problem-id]
#   [problem-id] Optional problem identifier (e.g., "p1-helloworld").
#                If omitted, all listed problems are run sequentially.
# Example:
#   ./sit.sh p1-helloworld
#   ./sit.sh   # runs all problems

set -euo pipefail

export PATH="/usr/local/share/dotnet:$HOME/.dotnet:$HOME/.cargo/bin:/opt/homebrew/bin:$PATH"

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [problem-id]"
  exit 1
fi

# Optional problem identifier; if empty, run all problems.
PROBLEM_ID="${1:-}" # optional; if empty run all problems

# ---------------------------------------------------------------------------
# Load problems from the catalog, filtering to those whose toolchains are
# installed. Emits "ID|GOAL" lines for available problems, and prints a
# skip notice for each unavailable one.
# ---------------------------------------------------------------------------
CATALOG="${MU_PROBLEMS_CATALOG:-$(dirname "$0")/problems-catalog.json}"

_load_available_problems() {
  python3 - "$CATALOG" <<'PYEOF'
import json, sys
from pathlib import Path

catalog_path = sys.argv[1]

# Locate mu package relative to the catalog file (../src/mu).
src = Path(catalog_path).resolve().parent / 'src'
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from mu.toolchain import available as toolchains_available, load_problems_catalog

try:
    problems = load_problems_catalog(catalog_path)
except Exception as e:
    print(f"Cannot read catalog {catalog_path}: {e}", file=sys.stderr)
    sys.exit(1)

avail = toolchains_available()
for p in problems:
    missing = set(p.get('toolchains', [])) - avail
    if missing:
        print(f"Skipping {p['id']} — toolchain not installed: {', '.join(sorted(missing))}", file=sys.stderr)
    else:
        print(f"{p['id']}|{p['goal']}")
PYEOF
}

# Build parallel arrays: PROBLEM_IDS and PROBLEM_GOALS
PROBLEM_IDS=()
PROBLEM_GOALS=()
while IFS='|' read -r pid pgoal; do
  PROBLEM_IDS+=("$pid")
  PROBLEM_GOALS+=("$pgoal")
done < <(_load_available_problems)

if [[ ${#PROBLEM_IDS[@]} -eq 0 ]]; then
  echo "No problems to run — install toolchains with: mu toolchain" >&2
  exit 1
fi

# Helpers so the rest of the script can look up a problem by ID.
get_goal() {
  local id="$1"
  for i in "${!PROBLEM_IDS[@]}"; do
    if [[ "${PROBLEM_IDS[$i]}" == "$id" ]]; then
      echo "${PROBLEM_GOALS[$i]}"
      return 0
    fi
  done
  return 1
}

problem_available() {
  local id="$1"
  for pid in "${PROBLEM_IDS[@]}"; do
    [[ "$pid" == "$id" ]] && return 0
  done
  return 1
}

# Shuffle the order so practice rounds don't always prime the model on p1's
# failure mode first. Skip when SIT_NO_SHUFFLE=1 (useful for reproducible
# single-run debugging) or when `shuf` is unavailable.
PROBLEMS=("${PROBLEM_IDS[@]}")
if [[ -z "${SIT_NO_SHUFFLE:-}" ]] && command -v shuf >/dev/null 2>&1; then
  mapfile -t PROBLEMS < <(printf '%s\n' "${PROBLEMS[@]}" | shuf)
fi

MU_CMD="mu"
# Prefer the project venv's mu if available so sit.sh works without activating the venv.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${SCRIPT_DIR}/.venv/bin/mu" ]]; then
  MU_CMD="${SCRIPT_DIR}/.venv/bin/mu"
fi

run_problem() {
  local folder="$1"
  local goal="$2"
  local workdir="./dojo/${folder}"
  if [ -z "${SKIP_CLEAN:-}" ]; then
    rm -rf "${workdir}"   # fresh dir prevents stale PLAN.md from a prior run
  fi
  mkdir -p "${workdir}"
  pushd "${workdir}" >/dev/null
  echo "Running problem '${folder}'"
  "${MU_CMD}" agent "${goal}" --dir . || true   # non-zero exit swallowed; outcome in session archive
  popd >/dev/null
}

echo "Warming up the model…"
"${MU_CMD}" model warm || echo "  (warm-up skipped — continuing cold)"

if [[ -n "${PROBLEM_ID}" ]]; then
  # Run a single specified problem.
  if ! problem_available "${PROBLEM_ID}"; then
    # Distinguish unknown ID from missing toolchain via the catalog.
    python3 - "$CATALOG" "${PROBLEM_ID}" <<'PYEOF'
import json, sys
from pathlib import Path
src = Path(sys.argv[1]).resolve().parent / 'src'
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
from mu.toolchain import load_problems_catalog
problems = load_problems_catalog(sys.argv[1])
ids = [p['id'] for p in problems]
if sys.argv[2] not in ids:
    print(f"Unknown problem ID: {sys.argv[2]}", file=sys.stderr)
    sys.exit(2)
else:
    print(f"Cannot run {sys.argv[2]} — required toolchain not installed. Run: mu toolchain", file=sys.stderr)
    sys.exit(1)
PYEOF
    exit $?
  fi
  GOAL=$(get_goal "${PROBLEM_ID}")
  run_problem "${PROBLEM_ID}" "${GOAL}"
else
  # Run all available problems from the catalog (shuffled).
  for folder in "${PROBLEMS[@]}"; do
    GOAL=$(get_goal "${folder}")
    run_problem "${folder}" "${GOAL}"
  done
fi

if [ -z "${SKIP_CLEAN:-}" ]; then
  echo "Cleaning dojo directory..."
  if [ -d "dojo" ]; then
    find dojo -mindepth 1 -maxdepth 1 -exec rm -rf {} + || true
  fi
else
  echo "Skipping dojo cleanup (SKIP_CLEAN is set)."
fi
