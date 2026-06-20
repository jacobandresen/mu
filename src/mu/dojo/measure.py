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
import re
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


# --- the whole-set board (plan Step 0.2 / §A.4): per-layer q̂ over all problems ---

# p10's four independent verification gates (a staged full-stack problem). Most
# problems are a single gate; only a dotnet+node full stack declares these four.
_P10_LAYERS = ('backend_build', 'backend_test', 'frontend_build', 'frontend_test')


def _problem_layers(problem: dict) -> tuple[str, ...]:
    """The verification layers a problem declares. A trivial problem (e.g.
    p1-helloworld) is a single gate, L=1; a staged dotnet+node full stack (p10) has
    four. Keyed on toolchains, not the id, so it generalizes."""
    tc = set(problem.get('toolchains') or [])
    if {'dotnet', 'node'} <= tc:
        return _P10_LAYERS
    return ('solved',)


def _p10_layer_clears(session_dir: Path) -> dict[str, bool]:
    """One p10 run's per-layer pass/fail, parsed from the staged gate logs (§A.4).
    Honest only because S1 (Step 0.1) makes a 'green' that ran no tests not a clear.
    A missing/garbled log reads as 'not cleared', never a crash."""
    try:
        text = '\n'.join(p.read_text(errors='ignore')
                         for p in (session_dir / 'logs').glob('*.log'))
    except OSError:
        text = ''
    return {
        'backend_build':  'Build succeeded' in text and 'error CS' not in text,
        'backend_test':   bool(re.search(r'Passed!\s+-\s+Failed:\s+0', text)),
        'frontend_build': 'vite build' in text and 'error TS' not in text,
        'frontend_test':  bool(re.search(r'Test Files\s+\d+ passed', text)),
    }


def _layer_clears(problem: dict, session) -> dict[str, bool]:
    """Per-layer pass/fail for one run. Single-gate problems clear iff the session
    succeeded; the full-stack stack reads its four layers from the logs."""
    layers = _problem_layers(problem)
    if layers == _P10_LAYERS:
        if session is None:
            return {l: False for l in _P10_LAYERS}
        return _p10_layer_clears(session.dir)
    return {'solved': bool(session and session.outcome == 'success')}


def board(emit_json: str = '', runs: int | None = None) -> int:
    """Run **all ten** problems over N fresh-plan runs and print the capability
    board: per-layer q̂, per-problem p_solve, the bottleneck layer, and the whole-set
    objective E[#solved] = Σ p_solve. The ranking + ledger instrument of plan §4.2."""
    from mu.toolchain import load_problems_catalog
    from .. import capability

    augment_path()
    n = runs if runs is not None else int(os.environ.get('N', '5'))
    problems = load_problems_catalog(None)
    subprocess.run(mu_cmd() + ['model', 'warm'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Board: measuring {len(problems)} problems over {n} run(s) each…\n")

    table: capability.Board = {}
    observed_solved = 0.0
    for problem in problems:
        pid, goal = problem['id'], problem['goal']
        layers = _problem_layers(problem)
        clears = {l: 0 for l in layers}
        solved = 0
        work = Path('dojo') / pid
        try:
            for i in range(1, n + 1):
                if work.exists():
                    shutil.rmtree(work)
                work.mkdir(parents=True)
                marker = now()
                subprocess.run(mu_cmd() + ['agent', goal, '--dir', str(work)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                s = sessions.latest_since(marker)
                solved += bool(s and s.outcome == 'success')
                lc = _layer_clears(problem, s)
                for l in layers:
                    if lc.get(l):
                        clears[l] += 1
        finally:
            if work.exists():
                shutil.rmtree(work)
        table[pid] = {l: capability.LayerStat(clears=clears[l], n=n) for l in layers}
        observed_solved += solved / n if n else 0.0
        print(f"  {pid:<26} solved {solved}/{n} · "
              f"layers " + ', '.join(f"{l}={clears[l]}/{n}" for l in layers))

    _print_board(table, observed_solved)

    if emit_json:
        import datetime, json as _json
        out = {
            'n': n,
            'e_solved': capability.e_solved(table),
            'raw_solved': _raw_solved(table),
            'observed_solved': observed_solved,
            'board': {
                pid: {
                    l: {'clears': st.clears, 'n': st.n,
                        'q': round(st.q, 4), 'ci': [round(c, 4) for c in st.ci]}
                    for l, st in layers.items()
                }
                for pid, layers in table.items()
            },
            'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        }
        Path(emit_json).write_text(_json.dumps(out, indent=2))
        print(f"\nBoard written to {emit_json}")
    return 0


def _raw_solved(table) -> float:
    """Σ over problems of the *raw* per-layer pass-product (clears/n, no smoothing).
    For a single-gate problem this is just its raw pass rate; the sum is the
    layer-parse's reconstruction of the observed solved count — the honest basis for
    the self-consistency check (the smoothed E[#solved] is biased high at small n
    because the Beta-Binomial prior lifts every 0/n layer off zero)."""
    total = 0.0
    for layers in table.values():
        prod = 1.0
        for st in layers.values():
            prod *= (st.clears / st.n) if st.n else 0.0
        total += prod
    return total


def _print_board(table, observed_solved: float) -> None:
    """Print per-problem p_solve + bottleneck, then the objective E[#solved] and the
    self-consistency check: the *raw* layer-parse must reproduce the observed
    (session-outcome) solved count, or the board isn't trustworthy (§0.2)."""
    from .. import capability
    print()
    for pid, layers in table.items():
        ps = capability.p_solve(layers)
        bn = capability.bottleneck(layers)
        bn_note = f" · bottleneck {bn} (q̂={layers[bn].q:.2f})" if len(layers) > 1 else ""
        print(f"  {pid:<26} p_solve={ps:.3f}{bn_note}")
    es = capability.e_solved(table)            # smoothed objective (Beta-Binomial)
    raw = _raw_solved(table)                    # raw layer-parse, for the check
    print(f"\nE[#solved] = {es:.2f} (smoothed)  ·  layer-parse {raw:.2f}  ·  "
          f"observed solved {observed_solved:.2f}")
    if abs(raw - observed_solved) <= 0.5:
        print("self-consistency OK: per-layer parse reproduces the observed solved count.")
    else:
        print("WARNING: per-layer parse diverges from observed — board not trustworthy.")


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
