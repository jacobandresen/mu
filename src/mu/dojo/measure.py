"""Measure ONE dojo problem over N runs — separate signal from stochastic noise.
(Port of measure.sh.)

Each run generates a fresh plan (mu plan) and then executes it (mu iterate), so
variance includes both the planner and the writer/repair layer. It reports pass
rate, average repair iterations (a continuous metric that moves with far fewer
runs than binary pass/fail), and a stochasticity score.

    python -m mu.dojo measure p7-flask           # N=5 runs
    N=10 python -m mu.dojo measure p7-flask
    MU_SEED=42 python -m mu.dojo measure p7-flask # pin the writer RNG (planner still samples)
"""

import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import sessions
from .env import augment_path, mu_cmd
from .sessions import now


def _goal(problem_id: str) -> str:
    from mu.toolchain import load_problems_catalog
    for p in load_problems_catalog(None):
        if p['id'] == problem_id:
            return p['goal']
    sys.exit(f"measure: unknown problem id: {problem_id}")


def run(problem_id: str, emit_json: str = '') -> int:
    augment_path()
    n = int(os.environ.get('N', '5'))
    seed = os.environ.get('MU_SEED', '')
    goal = _goal(problem_id)

    subprocess.run(mu_cmd() + ['model', 'warm'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    work = Path('dojo') / problem_id
    seed_note = f" (seed={seed}, temp 0)" if seed else ""
    disabled = os.environ.get('MU_DISABLE_REFLEX', '')
    abl_note = f" · reflex(es) DISABLED: {disabled}" if disabled else ""
    print(f"Measuring {problem_id} over {n} run(s) with fresh plan each run{seed_note}{abl_note}…")

    outcomes: list[str] = []
    repair_total = 0
    try:
        for i in range(1, n + 1):
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True)

            marker = now()
            subprocess.run(mu_cmd() + ['agent', goal, '--dir', str(work)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            s = sessions.latest_since(marker)
            outcome = s.outcome if s else '?'
            repair = s.repair_iters if s else 0
            outcomes.append(outcome)
            repair_total += repair
            mark = 'PASS' if outcome == 'success' else outcome
            print(f"  run {i}/{n}: {mark:<8} repair_iters={repair}")
    finally:
        if work.exists():
            shutil.rmtree(work)

    print()
    ok, stoch = _print_summary(problem_id, outcomes, repair_total, n, seed)

    if emit_json:
        import datetime, json as _json
        result = {
            'problem_id': problem_id,
            'seed': seed,
            'disabled': disabled,
            'n': n,
            'hits': ok,
            'pass_rate': ok / n if n else 0.0,
            'avg_repair_iters': repair_total / n if n else 0.0,
            'stochasticity': stoch,
            'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        }
        Path(emit_json).write_text(_json.dumps(result, indent=2))
        print(f"Result written to {emit_json}")

    return 0


def _print_summary(problem_id: str, outcomes: list[str], repair_total: int,
                   n: int, seed: str) -> tuple[int, float]:
    ok = sum(o == 'success' for o in outcomes)
    rate = 100 * ok // n if n else 0
    # Stochasticity: fraction of runs that differ from the most common outcome.
    # 0 = fully reproducible (every run identical); higher = noisier. With a seed
    # it should be ~0; unseeded, it is the intrinsic variance of this problem at
    # this minimization level (the number the ladder drives down — DOJO.md).
    modal = Counter(outcomes).most_common(1)[0][1] if outcomes else 0
    stoch = 1 - modal / n if n else 0
    note = f" · seed={seed}" if seed else " · sampled"
    print(f"{problem_id}: {ok}/{n} passed ({rate}%) · "
          f"avg repair iters {repair_total / n:.1f} · "
          f"stochasticity {stoch:.2f}{note}")
    return ok, stoch
