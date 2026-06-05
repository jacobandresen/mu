#!/usr/bin/env bash

# measure.sh — measure ONE dojo problem over N runs from a FROZEN plan, to
# separate signal from stochastic noise.
#
# The planner is the dominant variance source: a different decomposition each
# run changes everything downstream, so single-round pass/fail tells you almost
# nothing. This script removes that variance — it generates a golden PLAN.md
# once (cached under dojo/golden/<id>/), then runs `mu iterate` N times from a
# fresh copy of it, so the only thing varying is the writer/repair layer you are
# actually testing. It reports the pass rate AND the average repair iterations —
# a continuous metric that shifts smoothly and detects a real change with far
# fewer runs than binary pass/fail.
#
# Usage:
#   ./measure.sh p7-flask              # N=5 runs from the frozen plan
#   N=10 ./measure.sh p7-flask
#   MU_SEED=42 ./measure.sh p7-flask   # also pin the writer RNG (near-deterministic)
#   REGEN=1 ./measure.sh p7-flask      # regenerate (and overwrite) the golden plan
#
# Commit dojo/golden/<id>/PLAN.md to freeze the plan across sessions/machines.

set -uo pipefail

ID="${1:?usage: measure.sh <problem-id>   (N=, MU_SEED=, REGEN= via env)}"
N="${N:-5}"
ARCHIVE="${MU_AGENT_ARCHIVE_DIR:-$HOME/.mu/sessions}"
CATALOG="${MU_PROBLEMS_CATALOG:-$(dirname "$0")/problems-catalog.json}"
export PATH="/usr/local/share/dotnet:$HOME/.dotnet:$HOME/.cargo/bin:/opt/homebrew/bin:$PATH"
MU_CMD="mu"; [ -x ./.venv/bin/mu ] && MU_CMD="./.venv/bin/mu"

# Goal text from the catalog (same source sit.sh uses).
GOAL=$(python3 - "$CATALOG" "$ID" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).resolve().parent / 'src'))
from mu.toolchain import load_problems_catalog
for p in load_problems_catalog(sys.argv[1]):
    if p['id'] == sys.argv[2]:
        print(p['goal']); break
else:
    sys.exit(f"unknown problem id: {sys.argv[2]}")
PYEOF
)
[ -z "$GOAL" ] && { echo "measure.sh: no goal for '$ID'" >&2; exit 1; }

GOLDEN_DIR="dojo/golden/$ID"
GOLDEN="$GOLDEN_DIR/PLAN.md"

# Generate the golden plan once (or on REGEN). This is the only planner call.
if [ ! -f "$GOLDEN" ] || [ -n "${REGEN:-}" ]; then
  echo "Generating golden plan for $ID …"
  rm -rf "$GOLDEN_DIR"; mkdir -p "$GOLDEN_DIR"
  "$MU_CMD" plan "$GOAL" --dir "$GOLDEN_DIR" || { echo "measure.sh: mu plan failed" >&2; exit 1; }
  [ -f "$GOLDEN" ] || { echo "measure.sh: no PLAN.md produced" >&2; exit 1; }
  echo "Golden plan saved: $GOLDEN — commit it to freeze the planner."
fi

"$MU_CMD" model warm >/dev/null 2>&1 || true

marker=$(mktemp /tmp/measure-mark.XXXXXX)
trap 'rm -f "$marker"; rm -rf "dojo/$ID"' EXIT
pass=0; iters_sum=0
echo "Measuring $ID over $N run(s) from the frozen plan${MU_SEED:+ (seed=$MU_SEED, temp 0)}…"

for run in $(seq 1 "$N"); do
  rm -rf "dojo/$ID"; mkdir -p "dojo/$ID"
  cp "$GOLDEN" "dojo/$ID/PLAN.md"
  "$MU_CMD" iterate "$GOAL" --dir "dojo/$ID" >/dev/null 2>&1 || true

  meta=$(find "$ARCHIVE" -name meta.json -newer "$marker" 2>/dev/null \
         | xargs ls -t 2>/dev/null | head -1)
  touch "$marker"
  oc=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('outcome','?'))" "$meta" 2>/dev/null)
  ri=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('repair_iters',0))" "$meta" 2>/dev/null)
  iters_sum=$((iters_sum + ${ri:-0}))
  if [ "$oc" = "success" ]; then pass=$((pass + 1)); mark="PASS"; else mark="${oc:-?}"; fi
  outcomes="${outcomes}${oc:-?} "          # for the stochasticity metric
  printf '  run %d/%d: %-8s repair_iters=%s\n' "$run" "$N" "$mark" "${ri:-?}"
done

echo
python3 - "$ID" "$pass" "$N" "$iters_sum" "${MU_SEED:-}" "$outcomes" <<'PYEOF'
import sys
from collections import Counter
pid, ok, n, isum, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
outcomes = sys.argv[6].split()
rate = 100 * ok // n
# Stochasticity: fraction of runs that differ from the most common outcome.
# 0 = fully reproducible (every run identical); higher = noisier. With MU_SEED it
# should be ~0; unseeded, it is how much intrinsic variance this problem+level has
# (the metric the minimization ladder is meant to drive down — docs/PROBLEM_SPACE.md).
modal = Counter(outcomes).most_common(1)[0][1] if outcomes else 0
stoch = 1 - modal / n if n else 0
note = f" · seed={seed}" if seed else " · sampled (set MU_SEED to pin)"
print(f"{pid}: {ok}/{n} passed ({rate}%) · avg repair iters {isum/n:.1f} · "
      f"stochasticity {stoch:.2f} · plan frozen{note}")
PYEOF
