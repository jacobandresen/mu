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

# Evict all loaded models before loading the target, so no other model competes for RAM.
# This is critical on 8 GB machines where two 5 GB models cannot coexist.
curl -s http://localhost:11434/api/ps 2>/dev/null \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(m['name'])
" 2>/dev/null | while read -r model; do
    curl -s -m 30 -X POST http://localhost:11434/api/generate \
        -d "{\"model\":\"$model\",\"keep_alive\":0}" -o /dev/null 2>&1 || true
done

export MU_NUM_CTX=${MU_NUM_CTX:-6000}
export MU_NUM_KEEP=${MU_NUM_KEEP:-512}

# Warm up: load the agent model before mu starts.
# Derive the :agent model name from MU_AGENT_BASE_MODEL (strips the version tag, appends :agent).
# e.g. qwen3:8b → qwen3:agent, qwen2.5-coder:7b → qwen2.5-coder:agent
BASE_MODEL="${MU_AGENT_BASE_MODEL:-qwen2.5-coder:7b}"
BASE_FAMILY="${BASE_MODEL%%:*}"
WARMUP_MODEL="${MU_WARMUP_MODEL:-${BASE_FAMILY}:agent}"
WARMUP_CTX=$MU_NUM_CTX
curl -s -m 300 http://localhost:11434/api/generate \
    -d "{\"model\":\"$WARMUP_MODEL\",\"keep_alive\":\"30m\",\"options\":{\"num_ctx\":$WARMUP_CTX},\"stream\":false}" \
    -o /dev/null 2>&1 || true

cd "$DOJO/$DIR"
mu agent "$GOAL" 2>&1 | tee -a "$DOJO/$PROBLEM.log"
STATUS=${pipestatus[1]}
echo "=== $PROBLEM End: $(date +%s) (exit=$STATUS) ===" | tee -a "$DOJO/$PROBLEM.log"
exit $STATUS
