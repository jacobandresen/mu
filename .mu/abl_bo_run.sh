#!/bin/bash
# MU_BUILD_ORDER A/B — plan Step 0.6 / S6 proof obligation.
# Pre-registration: .mu/abl_bo_prereg.md  (p1/p2/p3, ON vs OFF, N=15).
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000
PY=.venv/bin/python
N=15
LOG=.mu/abl_bo.log

echo "=== build-order A/B start $(date) · model $MU_AGENT_MODEL · N=$N ===" | tee -a "$LOG"

arm() {  # problem  arm(on|off)
  local prob="$1" arm="$2"
  echo "--- $prob $arm ($(date)) ---" | tee -a "$LOG"
  if [ "$arm" = "on" ]; then
    MU_BUILD_ORDER=1 $PY -m mu.dojo measure "$prob" -n "$N" \
        --emit-json ".mu/abl_bo_${prob}_on.json" 2>&1 | tee -a "$LOG"
  else
    $PY -m mu.dojo measure "$prob" -n "$N" \
        --emit-json ".mu/abl_bo_${prob}_off.json" 2>&1 | tee -a "$LOG"
  fi
}

for prob in p1-helloworld p2-sqlite p3-sdl2; do
  arm "$prob" on
  arm "$prob" off
done

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_bo_analyze.py 2>&1 | tee -a "$LOG"
echo "=== build-order A/B complete $(date) ===" | tee -a "$LOG"
