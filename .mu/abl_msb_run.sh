#!/bin/bash
# MSB1003 test-command-redirect A/B — plan Step 0.5 backend_build.
# Pre-registration: .mu/abl_msb_prereg.md (model qwen-7b, N=15).
# The fix is a default-on code change (commit 8f82b34), NOT a runtime flag, so the
# OFF arm runs the PARENT commit's src/mu/plan.py, swapped in by git. Runs are
# sequential and each `mu dojo measure` spawns a fresh `python -m mu` subprocess,
# so the on-disk plan.py at launch time is what that arm uses. A trap always
# restores the fixed (HEAD) plan.py, even on interrupt.
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000
PY=.venv/bin/python
N=15
LOG=.mu/abl_msb.log
FILE=src/mu/plan.py
FIXED=$(mktemp)            # the HEAD (fixed) version, restored on exit

cp "$FILE" "$FIXED"
restore() { cp "$FIXED" "$FILE"; echo "--- restored fixed $FILE ---" | tee -a "$LOG"; }
trap restore EXIT

off() { git show HEAD~1:"$FILE" > "$FILE"; echo "--- OFF: pre-fix $FILE in place ---" | tee -a "$LOG"; }
on()  { cp "$FIXED" "$FILE";            echo "--- ON: fixed $FILE in place ---"    | tee -a "$LOG"; }

run() {  # arm-label  problem  emit-json
  echo "--- arm $1 ($(date)) ---" | tee -a "$LOG"
  $PY -m mu.dojo measure "$2" -n "$N" --emit-json "$3" 2>&1 | tee -a "$LOG"
}

echo "=== MSB1003 redirect A/B start $(date) · model $MU_AGENT_MODEL · N=$N ===" | tee -a "$LOG"

# p10 pair first (headline) so an interrupted run still yields the primary diff.
off; run p10-OFF p10-dotnet-vue-blog .mu/abl_msb_p10_off.json
on;  run p10-ON  p10-dotnet-vue-blog .mu/abl_msb_p10_on.json
off; run p4-OFF  p4-fibonacci        .mu/abl_msb_p4_off.json
on;  run p4-ON   p4-fibonacci        .mu/abl_msb_p4_on.json

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_msb_analyze.py 2>&1 | tee -a "$LOG"
echo "=== MSB1003 redirect A/B complete $(date) ===" | tee -a "$LOG"
