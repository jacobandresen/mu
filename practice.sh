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
#   ROUND_TIMEOUT=900 ./practice.sh        # kill any single round that exceeds this many seconds
#   SKIP_PREFLIGHT=1 ./practice.sh         # skip the LM Studio reachability check
#   SKIP_CLEAN=1 ./practice.sh             # keep dojo state between rounds (passes through to sit.sh)

set -uo pipefail

ROUNDS=${ROUNDS:-100}
STOP_AFTER_BARREN=${STOP_AFTER_BARREN:-5}
ARCHIVE=${MU_AGENT_ARCHIVE_DIR:-$HOME/.mu/sessions}
DIGEST=${DOJO_DIGEST:-dojo-failures.md}
REFLECT_LIMIT=${REFLECT_LIMIT:-10}
SKIP_REFLECT=${SKIP_REFLECT:-}
SKIP_PREFLIGHT=${SKIP_PREFLIGHT:-}
ROUND_TIMEOUT=${ROUND_TIMEOUT:-1800}
LMSTUDIO_HOST=${MU_LMSTUDIO_HOST:-http://localhost:1234}

export MU_ENRICH_LESSONS=1

MU_CMD="mu"

if ! command -v pi >/dev/null 2>&1; then
  echo "What is reality? look at pi.dev and return back"
  exit 1
fi

if [ ! -x ./sit.sh ]; then
  echo "practice.sh: ./sit.sh not found or not executable" >&2
  exit 1
fi

# Single-instance lock so two practice.sh can't race on the same dojo dir
# or the same session archive. flock(1) is the cheap, posix-y way.
LOCKFILE=${PRACTICE_LOCK:-/tmp/practice-$(id -u).lock}
exec 200>"$LOCKFILE"
if ! command -v flock >/dev/null 2>&1; then
  echo "practice.sh: flock not available; concurrency lock disabled" >&2
elif ! flock -n 200; then
  echo "practice.sh: another practice.sh is already running (lock: $LOCKFILE)" >&2
  exit 1
fi

# Preflight: confirm LM Studio is reachable. A round that runs against a
# dead endpoint burns one session per problem with no learning signal.
if [ -z "$SKIP_PREFLIGHT" ]; then
  if ! curl -sf --max-time 5 "${LMSTUDIO_HOST}/v1/models" >/dev/null 2>&1; then
    echo "practice.sh: LM Studio not reachable at ${LMSTUDIO_HOST}" >&2
    echo "  start it and load a model, or re-run with SKIP_PREFLIGHT=1" >&2
    exit 1
  fi
fi

# Warm the model once before the long rounds loop so the first round's first
# heavy request isn't cold. sit.sh also warms per round (cheap when already
# hot, and re-warms if the model was evicted between rounds). Best-effort.
echo "Warming up the model…"
"${MU_CMD}" model warm || echo "  (warm-up skipped — continuing)"

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

  # Wrap sit.sh in `timeout` so a single hung mu agent can't stall the
  # whole loop until manual intervention.
  if command -v timeout >/dev/null 2>&1; then
    timeout --foreground --kill-after=30s "${ROUND_TIMEOUT}" ./sit.sh || true
  else
    ./sit.sh || true
  fi

  successes=0
  failures=0
  failure_lines=$(mktemp)
  failed_ids=$(mktemp)

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
      [ -n "${sid:-}" ] && printf '%s\n' "$sid" >> "$failed_ids"
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
  # CHALLENGES.md. Scope to this round's failed session IDs so old
  # archived failures don't get re-processed each round.
  if [ "$failures" -gt 0 ] && [ -z "$SKIP_REFLECT" ]; then
    # shellcheck disable=SC2046 # word-splitting is intentional
    "${MU_CMD}" reflect -n "$REFLECT_LIMIT" $(cat "$failed_ids") || true
  fi
  rm -f "$failed_ids"

  # Commit any CHALLENGES.md updates reflect just made. Scoped commit
  # (via `git commit -o`) so unrelated dirty paths stay untouched.
  if [ -z "${SKIP_AUTOCOMMIT:-}" ] && git rev-parse --git-dir >/dev/null 2>&1; then
    if [ -f CHALLENGES.md ] && ! git diff-index --quiet HEAD -- CHALLENGES.md 2>/dev/null; then
      MU_VER=$(awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py)
      git commit -o CHALLENGES.md \
        -m "dojo round $round: record CHALLENGES.md updates (mu $MU_VER)" \
        >/dev/null || true
    fi
  fi

  # Empty rounds (zero sessions finalized at all) mean sit.sh aborted
  # before any problem completed — usually LM Studio went away mid-round
  # or `timeout` fired. Count them as barren; two in a row is a hard stop.
  if [ "$successes" -eq 0 ] && [ "$failures" -eq 0 ]; then
    barren_rounds=$((barren_rounds + 1))
    echo "round $round: empty (no sessions finalized) — counted as barren"
    if [ "$barren_rounds" -ge 2 ]; then
      echo "two empty rounds in a row — bailing"
      break
    fi
  elif [ "$successes" -eq 0 ] && [ "$failures" -gt 0 ]; then
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
