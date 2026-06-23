#!/bin/bash
# ASP.NET ENTRY-POINT lever A/B — plan Step 0.4 backend_build.
# Pre-registration: .mu/abl_ep_prereg.md (model qwen-7b, N=15).
# ON = MU_ASPNET_ENTRYPOINT=1, OFF = unset (the shipped default-off gate). All else at
# default — MU_S2_TYPE_REFLEXES held UNSET (single-variable ablation; S2 is the later
# re-eval). Sequential dark run; each arm spawns a fresh `python -m mu`. Auto-analyzes.
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000
unset MU_S2_TYPE_REFLEXES
PY=.venv/bin/python
N=15
LOG=.mu/abl_ep.log

run() {  # arm-label  problem  emit-json  entrypoint(on|off)
  if [ "$4" = on ]; then export MU_ASPNET_ENTRYPOINT=1; else unset MU_ASPNET_ENTRYPOINT; fi
  echo "--- arm $1 ($(date)) ENTRYPOINT=$4 ---" | tee -a "$LOG"
  $PY -m mu.dojo measure "$2" -n "$N" --emit-json "$3" 2>&1 | tee -a "$LOG"
}

echo "=== entry-point A/B start $(date) · model $MU_AGENT_MODEL · N=$N ===" | tee -a "$LOG"

# p10 pair first (headline) so an interrupted run still yields the primary diff.
run p10-EPon  p10-dotnet-vue-blog .mu/abl_ep_p10_on.json  on
run p10-EPoff p10-dotnet-vue-blog .mu/abl_ep_p10_off.json off
run p4-EPon   p4-fibonacci        .mu/abl_ep_p4_on.json   on
run p4-EPoff  p4-fibonacci        .mu/abl_ep_p4_off.json  off

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_ep_analyze.py 2>&1 | tee -a "$LOG"
echo "=== entry-point A/B complete $(date) ===" | tee -a "$LOG"
