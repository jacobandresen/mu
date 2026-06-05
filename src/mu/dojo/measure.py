"""Measure ONE dojo problem over N runs from a FROZEN plan — separate signal
from stochastic noise. (Port of measure.sh.)

The planner is the dominant variance source: a different decomposition each run
changes everything downstream, so single-round pass/fail tells you almost
nothing. This generates a golden ``PLAN.md`` once (cached under
``dojo/golden/<id>/``), then runs ``mu iterate`` N times from a fresh copy, so
the only thing varying is the writer/repair layer under test. It reports pass
rate, average repair iterations (a continuous metric that moves with far fewer
runs than binary pass/fail), and a stochasticity score.

    python -m mu.dojo measure p7-flask           # N=5 runs from the frozen plan
    N=10 python -m mu.dojo measure p7-flask
    MU_SEED=42 python -m mu.dojo measure p7-flask # also pin the writer RNG
    REGEN=1 python -m mu.dojo measure p7-flask    # regenerate the golden plan

Commit ``dojo/golden/<id>/PLAN.md`` to freeze the plan across machines.
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


def _ensure_golden(problem_id: str, goal: str, golden: Path) -> None:
    """Generate the golden plan once (or on REGEN). The only planner call."""
    if golden.exists() and not os.environ.get('REGEN'):
        return
    print(f"Generating golden plan for {problem_id} …")
    if golden.parent.exists():
        shutil.rmtree(golden.parent)
    golden.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(mu_cmd() + ['plan', goal, '--dir', str(golden.parent)])
    if r.returncode != 0 or not golden.exists():
        sys.exit("measure: mu plan failed to produce a PLAN.md")
    print(f"Golden plan saved: {golden} — commit it to freeze the planner.")


def run(problem_id: str) -> int:
    augment_path()
    n = int(os.environ.get('N', '5'))
    seed = os.environ.get('MU_SEED', '')
    goal = _goal(problem_id)
    golden = Path('dojo/golden') / problem_id / 'PLAN.md'
    _ensure_golden(problem_id, goal, golden)

    subprocess.run(mu_cmd() + ['model', 'warm'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    work = Path('dojo') / problem_id
    seed_note = f" (seed={seed}, temp 0)" if seed else ""
    print(f"Measuring {problem_id} over {n} run(s) from the frozen plan{seed_note}…")

    outcomes: list[str] = []
    repair_total = 0
    try:
        for i in range(1, n + 1):
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True)
            shutil.copy2(golden, work / 'PLAN.md')

            marker = now()
            subprocess.run(mu_cmd() + ['iterate', goal, '--dir', str(work)],
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
    _print_summary(problem_id, outcomes, repair_total, n, seed)
    return 0


def _print_summary(problem_id: str, outcomes: list[str], repair_total: int,
                   n: int, seed: str) -> None:
    ok = sum(o == 'success' for o in outcomes)
    rate = 100 * ok // n if n else 0
    # Stochasticity: fraction of runs that differ from the most common outcome.
    # 0 = fully reproducible (every run identical); higher = noisier. With a seed
    # it should be ~0; unseeded, it is the intrinsic variance of this problem at
    # this minimization level (the number the ladder drives down — PROBLEM_SPACE).
    modal = Counter(outcomes).most_common(1)[0][1] if outcomes else 0
    stoch = 1 - modal / n if n else 0
    note = f" · seed={seed}" if seed else " · sampled (set MU_SEED to pin)"
    print(f"{problem_id}: {ok}/{n} passed ({rate}%) · "
          f"avg repair iters {repair_total / n:.1f} · "
          f"stochasticity {stoch:.2f} · plan frozen{note}")
