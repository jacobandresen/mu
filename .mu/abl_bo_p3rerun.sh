#!/bin/bash
# Re-measure p3-sdl2 ON after the Makefile-weave fix (008d4ce), then refresh the
# A/B verdict. p3-OFF (15/15) and p1/p2 are unaffected, so only p3-ON is re-run.
set -u
cd "$(dirname "$0")/.." || exit 1
export MU_AGENT_MODEL=qwen2.5-coder-7b-instruct MU_NUM_CTX=6000
LOG=.mu/abl_bo.log
echo "=== p3-sdl2 ON re-measure (post-fix 008d4ce) $(date) ===" | tee -a "$LOG"
MU_BUILD_ORDER=1 .venv/bin/python -m mu.dojo measure p3-sdl2 -n 15 \
    --emit-json .mu/abl_bo_p3-sdl2_on.json 2>&1 | tee -a "$LOG"
echo "=== refreshing verdict $(date) ===" | tee -a "$LOG"
.venv/bin/python .mu/abl_bo_analyze.py 2>&1 | tee -a "$LOG"
echo "=== p3 re-measure complete $(date) ===" | tee -a "$LOG"
