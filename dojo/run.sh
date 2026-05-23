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

# Precondition: exactly one non-embedding model must be loaded.
ENSURE_OUT=$(mu model ensure-single 2>&1)
ENSURE_STATUS=$?
echo "==> [run.sh] $ENSURE_OUT" | tee -a "$DOJO/$PROBLEM.log"
if [ $ENSURE_STATUS -ne 0 ]; then
    echo "=== $PROBLEM End: $(date +%s) (exit=1) ===" | tee -a "$DOJO/$PROBLEM.log"
    exit 1
fi

rm -rf "$DOJO/$DIR"
mkdir -p "$DOJO/$DIR"

cd "$DOJO/$DIR"
mu agent "$GOAL" 2>&1 | tee -a "$DOJO/$PROBLEM.log"
STATUS=${pipestatus[1]}
echo "=== $PROBLEM End: $(date +%s) (exit=$STATUS) ===" | tee -a "$DOJO/$PROBLEM.log"
exit $STATUS
