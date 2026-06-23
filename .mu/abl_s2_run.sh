#!/bin/bash
# S2 cross-stage type-reflex ablation — plan Step 0.3 KEEP gate.
# Pre-registration: .mu/abl_s2_prereg.md  (model qwen-7b, N=15, 4 arms).
# Dark run (~6-8h on the 8 GB M2). Emits per-arm JSON, then the verdict.
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000
PY=.venv/bin/python
N=15
S2="fix_csharp_cross_stage_duplicate_types,fix_csharp_public_signature_accessibility"
LOG=.mu/abl_s2.log

echo "=== S2 ablation start $(date) · model $MU_AGENT_MODEL · N=$N ===" | tee -a "$LOG"

arm() {  # name  problem  emit  [disable]
  local name="$1" prob="$2" emit="$3" dis="${4:-}"
  echo "--- arm $name ($(date)) disable='${dis}' ---" | tee -a "$LOG"
  if [ -n "$dis" ]; then
    MU_DISABLE_REFLEX="$dis" $PY -m mu.dojo measure "$prob" -n "$N" --emit-json "$emit" 2>&1 | tee -a "$LOG"
  else
    $PY -m mu.dojo measure "$prob" -n "$N" --emit-json "$emit" 2>&1 | tee -a "$LOG"
  fi
}

# Headline first (p10), so an interrupted run still yields the primary result.
arm p10-ON  p10-dotnet-vue-blog .mu/abl_p10_s2on.json
arm p10-OFF p10-dotnet-vue-blog .mu/abl_p10_s2off.json "$S2"
arm p4-ON   p4-fibonacci        .mu/abl_p4_s2on.json
arm p4-OFF  p4-fibonacci        .mu/abl_p4_s2off.json "$S2"

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_analyze.py 2>&1 | tee -a "$LOG"
echo "=== S2 ablation complete $(date) ===" | tee -a "$LOG"
