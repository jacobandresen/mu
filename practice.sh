#!/usr/bin/env bash

# practice.sh — run repeated dojo rounds and learn from each one.
#
# Each round invokes sit.sh (which runs the full dojo problem set), then
# walks the session archive for every session finalized during the round
# and appends a structured digest to dojo-failures.md. Subsequent rounds
# benefit from prior failures via the enrich retriever
# (MU_ENRICH_LESSONS=1), so each round has more lesson material than the
# last.
#
# Usage:
#   ./practice.sh                          # 100 rounds, default behaviour
#   ROUNDS=10 ./practice.sh
#   STOP_AFTER_BARREN=3 ./practice.sh      # bail after N rounds with zero successes
#   SKIP_CLEAN=1 ./practice.sh             # keep dojo state between rounds (passes through to sit.sh)

set -uo pipefail

ROUNDS=${ROUNDS:-100}
STOP_AFTER_BARREN=${STOP_AFTER_BARREN:-5}
ARCHIVE=${MU_AGENT_ARCHIVE_DIR:-$HOME/.mu/sessions}
DIGEST=${DOJO_DIGEST:-dojo-failures.md}
REFLECT_LIMIT=${REFLECT_LIMIT:-10}
SKIP_REFLECT=${SKIP_REFLECT:-}

export MU_ENRICH_LESSONS=1

# Determine which mu binary to invoke (same precedence as sit.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${SCRIPT_DIR}/bin/mu" ]]; then
  MU_CMD="${SCRIPT_DIR}/bin/mu"
else
  MU_CMD="mu"
fi

if ! command -v pi >/dev/null 2>&1; then
  echo "What is reality? look at pi.dev and return back"
  exit 1
fi

if [ ! -x ./sit.sh ]; then
  echo "practice.sh: ./sit.sh not found or not executable" >&2
  exit 1
fi

echo "What is reality?"

# Marker file used to find sessions finalized within the current round.
marker=$(mktemp /tmp/practice-mark.XXXXXX)
trap 'rm -f "$marker"' EXIT

# Seed the digest header if missing.
if [ ! -f "$DIGEST" ]; then
  cat > "$DIGEST" <<EOF
# Dojo Practice Digest

One section per practice round. Each round lists the outcome of every
mu session finalized during the round. Failed sessions are listed by
goal so the next round's planner (which reads CHALLENGES.md and queries
the enrich retriever) has visible evidence of what failed and why.

EOF
fi

barren_rounds=0
total_ok=0
total_fail=0

for round in $(seq 1 "$ROUNDS"); do
  round_start=$(date +%s)
  printf '\n=== round %d/%d ===\n' "$round" "$ROUNDS"

  ./sit.sh || true

  successes=0
  failures=0
  failure_lines=$(mktemp)

  # Walk all sessions touched since the marker. -newer accounts for both
  # newly-created sessions and any whose meta.json was rewritten during
  # finalize().
  while IFS= read -r meta; do
    [ -z "$meta" ] && continue
    outcome=$(awk -F'"' '/"outcome"/{print $4; exit}' "$meta" 2>/dev/null)
    goal=$(awk -F'"' '/"goal"/{print $4; exit}' "$meta" 2>/dev/null)
    sid=$(awk -F'"' '/"session_id"/{print $4; exit}' "$meta" 2>/dev/null)
    if [ "$outcome" = "success" ]; then
      successes=$((successes + 1))
    else
      failures=$((failures + 1))
      printf -- '- **%s** (%s) — %s\n' "${outcome:-unknown}" "${sid:-?}" "${goal:-?}" \
        >> "$failure_lines"
    fi
  done < <(find "$ARCHIVE" -name meta.json -newer "$marker" 2>/dev/null)

  # Reset marker for the next round.
  touch "$marker"

  {
    printf '\n## round %d — %s\n' "$round" "$(date -Iseconds)"
    printf '\nsuccesses: %d  failures: %d\n\n' "$successes" "$failures"
    if [ -s "$failure_lines" ]; then
      printf 'Failed sessions:\n\n'
      cat "$failure_lines"
    fi
  } >> "$DIGEST"
  rm -f "$failure_lines"

  total_ok=$((total_ok + successes))
  total_fail=$((total_fail + failures))
  elapsed=$(( $(date +%s) - round_start ))
  printf 'round %d: %d ok / %d fail (%ds)  | cumulative %d ok / %d fail\n' \
    "$round" "$successes" "$failures" "$elapsed" "$total_ok" "$total_fail"

  # Reflect on this round's failures and append generic lessons to
  # CHALLENGES.md. Skipped when there were no failures, or when the
  # operator opts out with SKIP_REFLECT=1.
  if [ "$failures" -gt 0 ] && [ -z "$SKIP_REFLECT" ]; then
    "${MU_CMD}" reflect -n "$REFLECT_LIMIT" || true
  fi

  if [ "$successes" -eq 0 ] && [ "$failures" -gt 0 ]; then
    barren_rounds=$((barren_rounds + 1))
    if [ "$barren_rounds" -ge "$STOP_AFTER_BARREN" ]; then
      echo "no successes for $barren_rounds rounds — bailing out so a human can look"
      break
    fi
  else
    barren_rounds=0
  fi

  echo "mu!..."
done

printf '\npractice complete: %d ok / %d fail across %d round(s). Digest: %s\n' \
  "$total_ok" "$total_fail" "$round" "$DIGEST"
