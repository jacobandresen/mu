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
#   STOP_AFTER_BARREN=3 ./practice.sh      # bail after N rounds with zero successes (default 5)
#   ROUND_TIMEOUT=900 ./practice.sh        # kill any single round that exceeds this many seconds (default 1800)
#   SKIP_PREFLIGHT=1 ./practice.sh         # skip the LM Studio reachability check
#   SKIP_CLEAN=1 ./practice.sh             # keep dojo state between rounds (passes through to sit.sh)
#   SKIP_REFLECT=1 ./practice.sh           # skip the post-round reflect step
#   SKIP_AUTOCOMMIT=1 ./practice.sh        # skip auto-committing CHALLENGES.md after reflect
#   REFLECT_LIMIT=5 ./practice.sh          # max lessons written per reflect call (default 10)
#   DOJO_DIGEST=my.md ./practice.sh        # path for the per-round failure digest (default dojo-failures.md)
#   MU_AGENT_ARCHIVE_DIR=~/.mu/s ./practice.sh  # session archive dir (default ~/.mu/sessions)
#   MU_LMSTUDIO_HOST=http://host:1234 ./practice.sh  # LM Studio base URL for preflight check
#   PRACTICE_LOCK=/tmp/my.lock ./practice.sh     # override the single-instance lock file path

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
# Extend PATH with common tool install locations that may not be in the shell's
# default PATH (e.g. dotnet on macOS, Homebrew on Apple Silicon, Cargo).
# Directories that don't exist are ignored by the shell.
export PATH="/usr/local/share/dotnet:$HOME/.dotnet:$HOME/.cargo/bin:/opt/homebrew/bin:$PATH"

MU_CMD="mu"

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

# Distill the root cause of a failed session from its archived logs using mu's
# deterministic diagnose sensor (the same one that leads the repair prompt).
# Echoes a single one-line hint, or nothing. This turns the digest from
# "stalled: <goal>" into "stalled: <goal> -- cause: NameError 'app' not defined",
# so a human (or the next round's reflect step) sees the exact general-class
# error to turn into a reflex, instead of re-opening each session's logs by hand.
_root_cause() {
  local sdir="$1" log
  log=$(ls -t "$sdir"/logs/tests*.log 2>/dev/null | head -1)
  [ -z "$log" ] && log=$(ls -t "$sdir"/logs/lint*.log 2>/dev/null | head -1)
  [ -z "$log" ] && return 0
  python3 - "$log" <<'PYEOF' 2>/dev/null
import re, sys
try:
    from mu.diagnose import distill_test_errors
    txt = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    h = distill_test_errors(txt)
    if h:
        first = h.splitlines()[0]
        m = re.match(r'FOCUS[^:]*:\s*(.+)', first)  # single-hint form
        cause = m.group(1).strip() if m else ''
        if not cause:  # multi-hint form: first bullet under the header
            for ln in h.splitlines()[1:]:
                ln = ln.strip().lstrip('-').strip()
                if ln:
                    cause = ln
                    break
        if cause:
            print(cause)
except Exception:
    pass
PYEOF
}

# Warm the model once before the long rounds loop so the first round's first
# heavy request isn't cold. sit.sh also warms per round (cheap when already
# hot, and re-warms if the model was evicted between rounds). Best-effort.
echo "Warming up the model…"
"${MU_CMD}" model warm || echo "  (warm-up skipped — continuing)"

echo "What is reality?"

# Marker file used to find sessions finalized within the current round.
marker=$(mktemp /tmp/practice-mark.XXXXXX)
# Cumulative "outcome|problem-id" log across all rounds, for the per-problem
# pass-rate summary printed at the end (and appended to the digest).
results_all=$(mktemp /tmp/practice-results.XXXXXX)
failure_lines=''
failed_ids=''
trap 'rm -f "$marker" "$results_all" ${failure_lines:+$failure_lines} ${failed_ids:+$failed_ids}' EXIT

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
empty_rounds=0
total_ok=0
total_fail=0
practice_start=$(date +%s)

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
    # Problem id (p1-rust, p7-flask, …) from the session's project_dir basename —
    # more reliable than goal-text matching for the per-problem summary.
    pdir=$(awk -F'"' '/"project_dir"/{print $4; exit}' "$meta" 2>/dev/null)
    pid=$(basename "${pdir:-unknown}")
    printf '%s|%s\n' "${outcome:-unknown}" "${pid:-unknown}" >> "$results_all"
    if [ "$outcome" = "success" ]; then
      successes=$((successes + 1))
    else
      failures=$((failures + 1))
      # Distill the root cause from the session's archived logs so the digest
      # line names the general-class error, not just the goal.
      cause=$(_root_cause "$(dirname "$meta")")
      printf -- '- **%s** (%s) [%s] — %s%s\n' \
        "${outcome:-unknown}" "${sid:-?}" "${pid:-?}" "${goal:-?}" \
        "${cause:+ -- cause: $cause}" >> "$failure_lines"
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

  # Update the root token_usage.md summary after each round.
  "${MU_CMD}" token-report --output token_usage.md || true

  # Commit any CHALLENGES.md / token_usage.md updates. Scoped commit
  # (via `git commit -o`) so unrelated dirty paths stay untouched.
  if [ -z "${SKIP_AUTOCOMMIT:-}" ] && git rev-parse --git-dir >/dev/null 2>&1; then
    MU_VER=$(awk -F'"' '/__version__/ {print $2}' src/mu/__init__.py)
    COMMIT_FILES=()
    if [ -f CHALLENGES.md ] && ! git diff-index --quiet HEAD -- CHALLENGES.md 2>/dev/null; then
      COMMIT_FILES+=(CHALLENGES.md)
    fi
    if [ -f token_usage.md ] && { ! git ls-files --error-unmatch token_usage.md >/dev/null 2>&1 || ! git diff-index --quiet HEAD -- token_usage.md 2>/dev/null; }; then
      git add token_usage.md 2>/dev/null || true
      COMMIT_FILES+=(token_usage.md)
    fi
    if [ ${#COMMIT_FILES[@]} -gt 0 ]; then
      git commit -o "${COMMIT_FILES[@]}" \
        -m "dojo round $round: update CHALLENGES.md and token_usage.md (mu $MU_VER)" \
        >/dev/null || true
    fi
  fi

  # Track consecutive no-success rounds and consecutive empty rounds separately.
  # empty_rounds counts only truly empty rounds (no sessions at all — usually
  # LM Studio died or timeout fired); barren_rounds counts all no-success rounds
  # including empty ones. Both are reset on any success.
  if [ "$successes" -gt 0 ]; then
    barren_rounds=0
    empty_rounds=0
  else
    barren_rounds=$((barren_rounds + 1))
    if [ "$failures" -eq 0 ]; then
      empty_rounds=$((empty_rounds + 1))
      echo "round $round: empty (no sessions finalized) — counted as barren"
      if [ "$empty_rounds" -ge 2 ]; then
        echo "two empty rounds in a row — bailing"
        break
      fi
    else
      empty_rounds=0
    fi
    if [ "$barren_rounds" -ge "$STOP_AFTER_BARREN" ]; then
      echo "no successes for $barren_rounds rounds — bailing out so a human can look"
      break
    fi
  fi

  echo "mu!..."
done

total_elapsed=$(( $(date +%s) - practice_start ))
printf '\npractice complete: %d ok / %d fail across %d round(s) in %ds. Digest: %s\n' \
  "$total_ok" "$total_fail" "$round" "$total_elapsed" "$DIGEST"

# Per-problem pass-rate across the whole practice session. This is the signal
# for reflex iteration: a problem that fails round after round is a chronic
# general-class error to fix; one that's stochastic is closer to the model
# ceiling. Sorted worst-first so the highest-leverage target is on top.
if [ -s "$results_all" ]; then
  summary=$(awk -F'|' '
    { tot[$2]++; if ($1 == "success") ok[$2]++ }
    END {
      for (p in tot) {
        rate = (ok[p] + 0) / tot[p]
        printf "%.4f\t- %-16s %d/%d passed (%d%%)\n", rate, p, ok[p] + 0, tot[p], rate * 100 + 0.5
      }
    }' "$results_all" | sort -n | cut -f2-)
  printf '\nper-problem pass rate (worst first):\n%s\n' "$summary"
  {
    printf '\n## per-problem summary — %s\n\n' "$(date -Iseconds)"
    printf '%s\n' "$summary"
  } >> "$DIGEST"
fi
