#!/bin/zsh
# Run a single dojo problem. Called from the dojo session directory.
# Usage: dojo/run.sh <session-dir> <problem-id> <subdir> <goal>
#
# Example:
#   dojo/run.sh claude-gemma4-e2b-macos-m2-8gb-v0.7.0-2026-05-23 p1 p1-helloworld \
#     "write a hello world program in C. Use clang to compile it and run it."
#
# Requires LM Studio running with a model loaded. Set MU_LMSTUDIO_HOST if the
# server is not at the default http://localhost:1234.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SESSION=$1
PROBLEM=$2
DIR=$3
GOAL=$4
DOJO="$REPO/dojo/$SESSION"

echo "=== $PROBLEM Start: $(date +%s) ===" | tee "$DOJO/$PROBLEM.log"
rm -rf "$DOJO/$DIR"
mkdir -p "$DOJO/$DIR"

HOST="${MU_LMSTUDIO_HOST:-http://localhost:1234}"

# Verify LM Studio is reachable and report the loaded model.
MODELS=$(curl -s "$HOST/v1/models" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ids = [m['id'] for m in d.get('data', []) if 'embed' not in m['id']]
    print('\n'.join(ids))
except: pass
" 2>/dev/null)

if [ -z "$MODELS" ]; then
    echo "==> [run.sh] ERROR: LM Studio not reachable at $HOST" | tee -a "$DOJO/$PROBLEM.log"
    echo "=== $PROBLEM End: $(date +%s) (exit=1) ===" | tee -a "$DOJO/$PROBLEM.log"
    exit 1
fi

echo "==> [run.sh] LM Studio loaded models:" | tee -a "$DOJO/$PROBLEM.log"
echo "$MODELS" | while read -r m; do echo "==>   $m"; done | tee -a "$DOJO/$PROBLEM.log"

cd "$DOJO/$DIR"
mu agent "$GOAL" 2>&1 | tee -a "$DOJO/$PROBLEM.log"
STATUS=${pipestatus[1]}
echo "=== $PROBLEM End: $(date +%s) (exit=$STATUS) ===" | tee -a "$DOJO/$PROBLEM.log"
exit $STATUS
