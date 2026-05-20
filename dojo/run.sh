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


export MU_NUM_CTX=${MU_NUM_CTX:-3072}
export MU_NUM_KEEP=${MU_NUM_KEEP:-512}

# Derive the :mu model name from MU_AGENT_BASE_MODEL.
# e.g. qwen3:8b → qwen3:mu, qwen2.5-coder:7b → qwen2.5-coder:mu
BASE_MODEL="${MU_AGENT_BASE_MODEL:-qwen2.5-coder:7b}"
BASE_FAMILY="${BASE_MODEL%%:*}"
WARMUP_MODEL="${MU_WARMUP_MODEL:-${BASE_FAMILY}:mu}"

# Evict only OTHER loaded models — keep the target warm across runs.
# Evicting and reloading the target model causes Ollama to enter a stuck state
# on 8 GB machines where the double-load saturates RAM mid-request.
curl -s http://localhost:11434/api/ps 2>/dev/null \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    if m['name'] != '${WARMUP_MODEL}':
        print(m['name'])
" 2>/dev/null | while read -r model; do
    curl -s -m 30 -X POST http://localhost:11434/api/generate \
        -d "{\"model\":\"$model\",\"keep_alive\":0}" -o /dev/null 2>&1 || true
done

# Warm up: load the agent model if not already loaded.
WARMUP_T0=$(date +%s)
echo "==> [run.sh] Loading model: $WARMUP_MODEL ..." | tee -a "$DOJO/$PROBLEM.log"
curl -s -m 300 http://localhost:11434/api/generate \
    -d "{\"model\":\"$WARMUP_MODEL\",\"keep_alive\":\"30m\",\"stream\":false}" \
    -o /dev/null 2>&1 || true
WARMUP_SEC=$(( $(date +%s) - WARMUP_T0 ))
echo "==> [run.sh] Model ready: ${WARMUP_SEC}s" | tee -a "$DOJO/$PROBLEM.log"

cd "$DOJO/$DIR"
mu agent "$GOAL" 2>&1 | tee -a "$DOJO/$PROBLEM.log"
STATUS=${pipestatus[1]}
echo "=== $PROBLEM End: $(date +%s) (exit=$STATUS) ===" | tee -a "$DOJO/$PROBLEM.log"
exit $STATUS
