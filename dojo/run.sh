#!/bin/zsh
# Run a single dojo problem. Called from the dojo session directory.
# Usage: dojo/run.sh <session-dir> <problem-id> <subdir> <goal>
#
# Example:
#   dojo/run.sh claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-18 p4 p4-fibonacci \
#     "write the fibonacci sequence using C#. Use the dotnet command to compile C#."

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SESSION=$1
PROBLEM=$2
DIR=$3
GOAL=$4
DOJO="$REPO/dojo/$SESSION"

echo "=== $PROBLEM Start: $(date +%s) ===" | tee "$DOJO/$PROBLEM.log"
rm -rf "$DOJO/$DIR"
mkdir -p "$DOJO/$DIR"

# Warm up: one request to load the model before the agent starts
WARMUP_MODEL="${MU_WARMUP_MODEL:-qwen2.5-coder:agent}"
WARMUP_CTX=${MU_NUM_CTX:-4096}
curl -s -m 120 http://localhost:11434/api/generate \
    -d "{\"model\":\"$WARMUP_MODEL\",\"keep_alive\":\"30m\",\"options\":{\"num_ctx\":$WARMUP_CTX},\"stream\":false}" \
    -o /dev/null 2>&1 || true

cd "$DOJO/$DIR"
mu agent "$GOAL" 2>&1 | tee -a "$DOJO/$PROBLEM.log"
STATUS=${pipestatus[1]}
echo "=== $PROBLEM End: $(date +%s) (exit=$STATUS) ===" | tee -a "$DOJO/$PROBLEM.log"
exit $STATUS
