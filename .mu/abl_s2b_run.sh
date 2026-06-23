#!/bin/bash
# S2 RE-EVALUATION (post-MSB1003-fix) — plan Step 0.3.
# Pre-registration: .mu/abl_s2b_prereg.md (qwen-7b, N=15).
# S2 ON = MU_S2_TYPE_REFLEXES=1, OFF = unset (the shipped opt-in gate). All else at
# default — MU_ASPNET_ENTRYPOINT stays UNSET (single-variable ablation). Sequential
# dark run; each arm spawns a fresh `python -m mu`. Auto-analyzes at the end.
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000
unset MU_ASPNET_ENTRYPOINT
PY=.venv/bin/python
N=15
LOG=.mu/abl_s2b.log

run() {  # arm-label  problem  emit-json  s2(on|off)
  if [ "$4" = on ]; then export MU_S2_TYPE_REFLEXES=1; else unset MU_S2_TYPE_REFLEXES; fi
  echo "--- arm $1 ($(date)) S2=$4 ---" | tee -a "$LOG"
  $PY -m mu.dojo measure "$2" -n "$N" --emit-json "$3" 2>&1 | tee -a "$LOG"
}

echo "=== S2 re-eval start $(date) · model $MU_AGENT_MODEL · N=$N ===" | tee -a "$LOG"

# p10 pair first (headline) so an interrupted run still yields the primary diff.
run p10-S2on  p10-dotnet-vue-blog .mu/abl_s2b_p10_on.json  on
run p10-S2off p10-dotnet-vue-blog .mu/abl_s2b_p10_off.json off
run p4-S2on   p4-fibonacci        .mu/abl_s2b_p4_on.json   on
run p4-S2off  p4-fibonacci        .mu/abl_s2b_p4_off.json  off

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_s2b_analyze.py 2>&1 | tee -a "$LOG"
echo "=== S2 re-eval complete $(date) ===" | tee -a "$LOG"
