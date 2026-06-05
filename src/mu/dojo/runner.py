"""Run the dojo problems — one, or all of them. (Port of sit.sh.)

Loads the catalog, drops problems whose toolchains aren't installed, and runs
each remaining one through ``mu agent``. Two opt-in minimization levers wrap the
run (docs/PROBLEM_SPACE.md): competence **routing** (``MU_ROUTE`` skips a problem
the chosen model is measured hopeless on) and **fixtures** (committed boilerplate
copied in so the model can't write it wrong).

    python -m mu.dojo run                 # all available problems (shuffled)
    python -m mu.dojo run p1-helloworld   # just one

Environment:
    MU_NUM_CTX=8192     context ceiling for the dojo's small model (default here)
    MU_ROUTE=1          enable competence routing (needs MU_AGENT_MODEL)
    MU_AGENT_MODEL=…    model id, for routing
    SKIP_CLEAN=1        keep dojo state between runs (don't wipe work dirs)
    SIT_NO_SHUFFLE=1    run in catalog order (reproducible single-run debugging)
"""

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

from .. import fixtures
from ..toolchain import available, load_problems_catalog
from .env import augment_path, mu_cmd

_DOJO = Path('dojo')


def _skip_notices() -> None:
    """Print one notice per problem dropped for a missing toolchain — the same
    visibility sit.sh gave, so a skipped problem isn't silently absent."""
    have = available()
    for p in load_problems_catalog(None):
        missing = set(p.get('toolchains', [])) - have
        if missing:
            print(f"Skipping {p['id']} — toolchain not installed: "
                  f"{', '.join(sorted(missing))}", file=sys.stderr)


def _routed_out(problem_id: str) -> bool:
    """True when MU_ROUTE is on and the model is measured hopeless on this
    problem's toolchains — don't burn a round generating noise."""
    model = os.environ.get('MU_AGENT_MODEL', '')
    if not os.environ.get('MU_ROUTE') or not model:
        return False
    return fixtures.should_skip_problem(model, problem_id)


def run_problem(problem_id: str, goal: str) -> None:
    work = _DOJO / problem_id

    if _routed_out(problem_id):
        print(f"Routing: skipping '{problem_id}' — {os.environ['MU_AGENT_MODEL']} "
              f"is measured hopeless on its toolchain.")
        return

    if not os.environ.get('SKIP_CLEAN') and work.exists():
        shutil.rmtree(work)          # fresh dir prevents a stale PLAN.md
    work.mkdir(parents=True, exist_ok=True)

    provided = fixtures.apply(problem_id, str(work))
    if provided:
        print(f"Fixtures provided for '{problem_id}': {' '.join(provided)}")

    print(f"Running problem '{problem_id}'")
    # cwd=work + `--dir .` matches sit.sh's pushd; non-zero is swallowed — the
    # outcome is recorded in the session archive, not the exit code.
    subprocess.run(mu_cmd() + ['agent', goal, '--dir', '.'], cwd=work)


# Committed inputs that live under dojo/ but must survive cleanup. sit.sh's
# `find dojo -mindepth 1 -maxdepth 1 -exec rm -rf` wiped these (the recurring
# "golden plans deleted" footgun); the port spares them on purpose.
_PROTECTED = {'golden', 'fixtures'}


def _cleanup() -> None:
    if os.environ.get('SKIP_CLEAN'):
        print("Skipping dojo cleanup (SKIP_CLEAN is set).")
        return
    print("Cleaning dojo directory...")
    if _DOJO.is_dir():
        for child in _DOJO.iterdir():
            if child.name in _PROTECTED:
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()


def run(problem_id: str = '') -> int:
    augment_path()
    # The dojo targets the small granite model; a larger window than the 6000
    # default avoids HTTP 400s when a repair prompt exceeds LM Studio's 4096 JIT.
    os.environ.setdefault('MU_NUM_CTX', '8192')

    catalog = load_problems_catalog(None)
    have = available()
    by_id = {p['id']: p['goal'] for p in catalog}
    avail_ids = [p['id'] for p in catalog if set(p.get('toolchains', [])) <= have]
    _skip_notices()

    if problem_id:
        if problem_id not in by_id:
            print(f"Unknown problem ID: {problem_id}", file=sys.stderr)
            return 2
        if problem_id not in avail_ids:
            print(f"Cannot run {problem_id} — required toolchain not installed. "
                  f"Run: mu toolchain", file=sys.stderr)
            return 1
        order = [problem_id]
    else:
        if not avail_ids:
            print("No problems to run — install toolchains with: mu toolchain", file=sys.stderr)
            return 1
        order = list(avail_ids)
        # Shuffle so practice rounds don't always prime the model on p1 first.
        if not os.environ.get('SIT_NO_SHUFFLE'):
            random.shuffle(order)

    print("Warming up the model…")
    subprocess.run(mu_cmd() + ['model', 'warm'])

    for pid in order:
        run_problem(pid, by_id[pid])

    _cleanup()                   # runs in both modes, like sit.sh
    return 0
