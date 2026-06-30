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
import signal
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import sessions
from .env import augment_path, mu_cmd
from .sessions import now


def _problem(problem_id: str) -> dict:
    from mu.toolchain import load_problems_catalog
    for p in load_problems_catalog(None):
        if p['id'] == problem_id:
            return p
    sys.exit(f"measure: unknown problem id: {problem_id}")


def _goal(problem_id: str) -> str:
    return _problem(problem_id)['goal']


def _run_agent(goal: str, work: Path) -> None:
    """Run `mu agent` with a per-run timeout (ROUND_TIMEOUT, default 1800s).
    SIGTERM the process group on timeout, escalating to SIGKILL if needed."""
    round_timeout = int(os.environ.get('ROUND_TIMEOUT', '1800'))
    proc = subprocess.Popen(
        mu_cmd() + ['agent', goal, '--dir', str(work)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        proc.wait(timeout=round_timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        print(f"  agent exceeded {round_timeout}s — killed", file=sys.stderr)


def _rmwork(path: Path) -> None:
    """Remove a dojo work dir, tolerating undeletable entries (e.g. a node_modules
    tree whose read-only files make ``shutil.rmtree`` raise 'Directory not empty'
    mid-walk). A measurement board must never crash on cleanup — fall back to a
    forced ``rm -rf`` and otherwise swallow the error."""
    if not path.exists():
        return
    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        subprocess.run(['rm', '-rf', str(path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(problem_id: str, emit_json: str = '') -> int:
    augment_path()
    n = int(os.environ.get('N', '5'))
    seed = os.environ.get('MU_SEED', '')
    problem = _problem(problem_id)
    goal = problem['goal']
    layers = _problem_layers(problem)

    subprocess.run(mu_cmd() + ['model', 'warm'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    work = Path('dojo') / problem_id
    seed_note = f" (seed={seed}, temp 0)" if seed else ""
    disabled = os.environ.get('MU_DISABLE_REFLEX', '')
    abl_note = f" · reflex(es) DISABLED: {disabled}" if disabled else ""
    print(f"Measuring {problem_id} over {n} run(s) with fresh plan each run{seed_note}{abl_note}…")

    outcomes: list[str] = []
    repair_total = 0
    layer_clears = {l: 0 for l in layers}
    try:
        for i in range(1, n + 1):
            _rmwork(work)
            work.mkdir(parents=True, exist_ok=True)

            marker = now()
            _run_agent(goal, work)

            s = sessions.latest_since(marker)
            outcome = s.outcome if s else '?'
            repair = s.repair_iters if s else 0
            outcomes.append(outcome)
            repair_total += repair
            lc = _layer_clears(problem, s)
            for l in layers:
                if lc.get(l):
                    layer_clears[l] += 1
            mark = 'PASS' if outcome == 'success' else outcome
            layer_note = ('  ' + ' '.join(f"{l}={'✓' if lc.get(l) else '·'}"
                                          for l in layers)) if len(layers) > 1 else ''
            print(f"  run {i}/{n}: {mark:<8} repair_iters={repair}{layer_note}")
    finally:
        _rmwork(work)

    print()
    ok, stoch = _print_summary(problem_id, outcomes, repair_total, n, seed)
    if len(layers) > 1:
        from .. import capability
        stats = {l: capability.LayerStat(clears=layer_clears[l], n=n) for l in layers}
        bn = capability.bottleneck(stats)
        print("  per-layer q̂: " + ' · '.join(
            f"{l} {layer_clears[l]}/{n} (q̂={stats[l].q:.2f})" for l in layers)
            + f"  · bottleneck {bn}")

    if emit_json:
        import datetime, json as _json
        from .. import capability
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
        # Always emit smoothed layers + p_solve (even for single-layer problems) so a
        # consumer comparing this against a board entry uses the *same* Beta-Binomial
        # scale on both sides — a raw pass_rate vs a smoothed q̂ would manufacture phantom
        # deltas (a no-op 3/3 re-measure reads 1.0 against a baseline q̂≈0.8).
        stats = {l: capability.LayerStat(clears=layer_clears[l], n=n) for l in layers}
        result['layers'] = {
            l: {'clears': layer_clears[l], 'n': n,
                'q': round(stats[l].q, 4), 'ci': [round(c, 4) for c in stats[l].ci]}
            for l in layers
        }
        result['p_solve'] = round(capability.p_solve(stats), 4)
        result['bottleneck'] = capability.bottleneck(stats)
        Path(emit_json).write_text(_json.dumps(result, indent=2))
        print(f"Result written to {emit_json}")

    return 0


def _next_archive_dir(archive: Path) -> Path:
    """Return archive/<NNN> where NNN is one higher than any existing numeric entry."""
    existing = [int(p.name) for p in archive.iterdir() if p.is_dir() and p.name.isdigit()] \
        if archive.exists() else []
    next_id = max(existing, default=0) + 1
    return archive / f"{next_id:03d}"


def _write_archive_readme(archive_dir: Path, n: int, table=None) -> None:
    import datetime
    import json as _json
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        git_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_hash = 'unknown'

    # Collect applied improvements from the sit attempt log written since the
    # previous archive run, so analysis mode can see what was already tried.
    improvements = ''
    log_file = Path('.mu') / 'sit_history' / 'attempts.jsonl'
    if log_file.exists():
        prev_num = int(archive_dir.name) - 1
        prev_ts = ''
        if prev_num > 0:
            prev_readme = archive_dir.parent / f"{prev_num:03d}" / 'README.md'
            if prev_readme.exists():
                import re as _re
                m = _re.search(r'\*\*date\*\*: (.+)', prev_readme.read_text())
                if m:
                    prev_ts = m.group(1).strip()
        seen = set()
        lines = []
        for raw in log_file.read_text().splitlines():
            try:
                r = _json.loads(raw)
            except Exception:
                continue
            if r.get('outcome') != 'applied':
                continue
            if prev_ts and r.get('ts', '') <= prev_ts:
                continue
            key = (r.get('file', ''), r.get('rationale', ''))
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- `{r['file']}` — {r['rationale']}"
                + (f" (targets: {', '.join(r['target_problems'])})" if r.get('target_problems') else '')
            )
        if lines:
            improvements = '\n## Implemented improvements\n\n' + '\n'.join(lines) + '\n'

    results = ''
    if table:
        from .. import capability as _cap
        rows = []
        for pid, layers in table.items():
            p_solve = round(_cap.p_solve(layers), 4)
            fix_rate = f"{p_solve:.0%}"
            layer_detail = ', '.join(
                f"{l}={st.clears}/{st.n}" for l, st in layers.items()
                if l != 'solved'
            )
            row = f"| {pid} | {fix_rate} |"
            if layer_detail:
                row += f" {layer_detail} |"
            rows.append(row)
        header = '| problem | fix rate |\n|---------|----------|\n'
        results = '\n## Results\n\n' + header + '\n'.join(rows) + '\n'

    (archive_dir / 'README.md').write_text(
        f"# Board run {archive_dir.name}\n\n"
        f"- **date**: {ts}\n"
        f"- **git**: `{git_hash}`\n"
        f"- **runs per problem**: {n}\n"
        + results
        + improvements
    )


def _write_run_readme(dest: Path, pid: str, run_num: int,
                      solved: bool, s) -> None:
    """Write a per-run README.md inside the archived problem directory."""
    status = "SOLVED" if solved else "NOT SOLVED"
    lines = [
        f"# {pid} — run {run_num}",
        "",
        f"**Result:** {status}",
        "",
    ]
    if not solved:
        # Try to extract a useful error from tests-final.log first, then agent.log.
        error_text = ""
        for log_name in ("tests-final.log", "agent.log"):
            log_path = dest / ".mu" / log_name
            if log_path.exists():
                text = log_path.read_text(errors="replace").strip()
                if text:
                    error_text = text
                    break
        if error_text:
            # Keep last 4000 chars so the README stays readable.
            if len(error_text) > 4000:
                error_text = "…(truncated)\n" + error_text[-4000:]
            lines += ["## Error", "", "```", error_text, "```", ""]
        elif s is not None:
            outcome = getattr(s, "outcome", "unknown")
            lines += [f"**Outcome:** {outcome}", ""]
    (dest / "README.md").write_text("\n".join(lines), encoding="utf-8")


# --- the whole-set board (plan Step 0.2 / §A.4): per-layer q̂ over all problems ---

# p15's two independent verification gates (dotnet+node full-stack). Most
# problems are a single gate; p15 uses a prototype-then-refine model.
_P15_LAYERS = ('prototype', 'refine')


def _problem_layers(problem: dict) -> tuple[str, ...]:
    """The verification layers a problem declares. A trivial problem (e.g.
    p1-helloworld) is a single gate, L=1; p15-dotnet-vue-blog uses a two-layer
    prototype-then-refine model. Keyed on toolchains, not the id, so it generalizes."""
    tc = set(problem.get('toolchains') or [])
    if {'dotnet', 'node'} <= tc:
        return _P15_LAYERS
    return ('solved',)


def _p15_layer_clears(session_dir: Path) -> dict[str, bool]:
    """One p15 run's per-layer pass/fail, parsed from the staged gate logs (§A.4).
    Honest only because S1 (Step 0.1) makes a 'green' that ran no tests not a clear.
    A missing/garbled log reads as 'not cleared', never a crash.
    
    prototype: dotnet build succeeds with no C# compiler errors
    refine: dotnet test passes + frontend builds and tests pass
    """
    try:
        text = '\n'.join(p.read_text(errors='ignore')
                         for p in (session_dir / 'logs').glob('*.log'))
    except OSError:
        text = ''
    return {
        'prototype': 'Build succeeded' in text and 'error CS' not in text,
        'refine': bool(re.search(r'Passed!\s+-\s+Failed:\s+0', text)) and 
                  ('vite build' in text and 'error TS' not in text) and
                  bool(re.search(r'Test Files\s+\d+ passed', text)),
    }


def _layer_clears(problem: dict, session) -> dict[str, bool]:
    """Per-layer pass/fail for one run. Single-gate problems clear iff the session
    succeeded; p15 reads its two layers from the logs."""
    layers = _problem_layers(problem)
    if layers == _P15_LAYERS:
        if session is None:
            return {l: False for l in _P15_LAYERS}
        return _p15_layer_clears(session.dir)
    return {'solved': bool(session and session.outcome == 'success')}


def board(emit_json: str = '', runs: int | None = None) -> int:
    """Run **all ten** problems over N fresh-plan runs and print the capability
    board: per-layer q̂, per-problem p_solve, the bottleneck layer, and the whole-set
    objective E[#solved] = Σ p_solve. The ranking + ledger instrument of plan §4.2."""
    import json as _json
    from mu.toolchain import load_problems_catalog
    from .. import capability

    augment_path()
    n = runs if runs is not None else int(os.environ.get('N', '5'))
    problems = load_problems_catalog(None)
    subprocess.run(mu_cmd() + ['model', 'warm'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Board: measuring {len(problems)} problems over {n} run(s) each…\n")

    archive_root = _next_archive_dir(Path('archive'))
    archive_root.mkdir(parents=True, exist_ok=True)
    _write_archive_readme(archive_root, n)
    print(f"Archiving runs to {archive_root}/\n")

    table: capability.Board = {}
    causes: dict[str, dict[str, int]] = {}
    observed_solved = 0.0
    for problem in problems:
        pid, goal = problem['id'], problem['goal']
        layers = _problem_layers(problem)
        clears = {l: 0 for l in layers}
        cause_counts: dict[str, int] = {}
        solved = 0
        work = Path('dojo') / pid
        save_root = os.environ.get('MU_DOJO_SAVE_RUNS', '')
        try:
            for i in range(1, n + 1):
                _rmwork(work)
                work.mkdir(parents=True, exist_ok=True)
                marker = now()
                _run_agent(goal, work)
                s = sessions.latest_since(marker)
                solved += bool(s and s.outcome == 'success')
                if s and s.outcome != 'success':
                    cause = sessions.root_cause(s.dir) or s.outcome
                    cause_counts[cause] = cause_counts.get(cause, 0) + 1
                lc = _layer_clears(problem, s)
                for l in layers:
                    if lc.get(l):
                        clears[l] += 1
                dest = archive_root / pid / str(i)
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(work, dest, dirs_exist_ok=True)
                _write_run_readme(dest, pid, i, bool(s and s.outcome == 'success'), s)
                if save_root:
                    save_dest = Path(save_root) / pid / str(i)
                    _rmwork(save_dest)
                    shutil.copytree(work, save_dest, dirs_exist_ok=True)
        finally:
            _rmwork(work)
        table[pid] = {l: capability.LayerStat(clears=clears[l], n=n) for l in layers}
        causes[pid] = dict(sorted(cause_counts.items(), key=lambda kv: -kv[1]))
        observed_solved += solved / n if n else 0.0
        # Checkpoint the partial board to disk *before* printing the per-problem summary.
        # The sit.py loop matches that printed "solved X/3" line and immediately kills this
        # process on an early-stop trigger, so the triggering problem must already be
        # persisted — otherwise analysis never sees the very problem that stopped the run.
        if emit_json:
            Path(emit_json).write_text(
                _json.dumps(_board_payload(n, table, causes, observed_solved,
                                           partial=True), indent=2))
        print(f"  {pid:<26} solved {solved}/{n} · "
              f"layers " + ', '.join(f"{l}={clears[l]}/{n}" for l in layers))

    _print_board(table, observed_solved)
    _write_archive_readme(archive_root, n, table)

    if emit_json:
        Path(emit_json).write_text(
            _json.dumps(_board_payload(n, table, causes, observed_solved,
                                       partial=False), indent=2))
        print(f"\nBoard written to {emit_json}")
    return 0


def _board_payload(n: int, table: 'capability.Board', causes: dict,
                   observed_solved: float, partial: bool) -> dict:
    """Serialize the (possibly partial) board + per-problem first-error tallies."""
    import datetime
    from .. import capability
    return {
        'n': n,
        'partial': partial,
        'problems_done': len(table),
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
        'first_errors': causes,
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
    }


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
