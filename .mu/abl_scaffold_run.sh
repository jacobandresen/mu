#!/bin/bash
# SCAFFOLD lever A/B — scaffolding.md §5 backend_build.
# Pre-registration: .mu/abl_scaffold_prereg.md (model qwen-7b, N=15).
# ON  = MU_SCAFFOLD=1 + MU_SCAFFOLD_STACKS=dotnet-webapi,dotnet-xunit (prevent side)
# OFF = all scaffold/tfm env unset (shipped default-off, byte-identical)
# TFM = MU_TFM_GROUNDING=1, scaffold unset (Arm 3 — the repair-side substitute)
# Single variable; confounders (entry-point, S2) held UNSET. Fresh `mu agent` per run.
set -u
cd "$(dirname "$0")/.." || exit 1

export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct
export MU_NUM_CTX=6000   # qwen sweet spot (MODELS.md) + matches every prior ablation
PY=.venv/bin/python
[ -x "$PY" ] || PY=python
N="${N:-15}"
LOG=.mu/abl_scaffold.log

run() {  # arm-label  problem  emit-json  mode(scaffold|baseline|tfm)
  unset MU_SCAFFOLD MU_SCAFFOLD_STACKS MU_TFM_GROUNDING
  unset MU_ASPNET_ENTRYPOINT MU_S2_TYPE_REFLEXES   # held off (confounders)
  case "$4" in
    scaffold) export MU_SCAFFOLD=1 MU_SCAFFOLD_STACKS=dotnet-webapi,dotnet-xunit ;;
    tfm)      export MU_TFM_GROUNDING=1 ;;
    baseline) : ;;
  esac
  echo "--- arm $1 ($(date)) mode=$4 N=$N ---" | tee -a "$LOG"
  N="$N" $PY -m mu.dojo measure "$2" -n "$N" --emit-json "$3" 2>&1 | tee -a "$LOG"
}

echo "=== SCAFFOLD A/B start $(date) · model $MU_AGENT_MODEL · N=$N · mode=${HEADLINE:+headline}${HEADLINE:-full} ===" | tee -a "$LOG"

# Headline pair first so an interrupted run still yields the primary P1 diff.
run p10-SCAFon  p10-dotnet-vue-blog .mu/abl_scaffold_p10_on.json   scaffold
run p10-SCAFoff p10-dotnet-vue-blog .mu/abl_scaffold_p10_off.json  baseline

# HEADLINE=1 stops here (just the P1 default-on decision). Each p10 run is slow
# (architect + 3 staged build/test/repair loops), so the controls + Arm 3 are the
# expensive long tail — run the full sweep only when there is time for ~8-12h.
if [ -z "${HEADLINE:-}" ]; then
  # Arm 3 — prevent vs repair at the same wall (compared against p10-SCAFon).
  run p10-TFM     p10-dotnet-vue-blog .mu/abl_scaffold_p10_tfm.json  tfm
  # Control — dotnet, recipe-eligible (xunit) but a single-project goal.
  run p4-SCAFon   p4-fibonacci        .mu/abl_scaffold_p4_on.json    scaffold
  run p4-SCAFoff  p4-fibonacci        .mu/abl_scaffold_p4_off.json   baseline
  # Controls — non-dotnet; the recipe must NEVER fire (scaffold==null every run).
  run p1-SCAFon   p1-helloworld       .mu/abl_scaffold_p1_on.json    scaffold
  run p1-SCAFoff  p1-helloworld       .mu/abl_scaffold_p1_off.json   baseline
  run p2-SCAFon   p2-sqlite           .mu/abl_scaffold_p2_on.json    scaffold
  run p2-SCAFoff  p2-sqlite           .mu/abl_scaffold_p2_off.json   baseline
fi

echo "=== arms done $(date) — analyzing ===" | tee -a "$LOG"
$PY .mu/abl_scaffold_analyze.py 2>&1 | tee -a "$LOG"
echo "=== SCAFFOLD A/B complete $(date) ===" | tee -a "$LOG"
