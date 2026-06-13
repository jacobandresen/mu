"""Run repeated dojo rounds and learn from each one. (Port of practice.sh.)

Each round runs the full problem set (``python -m mu.dojo run``), then reflects
failures into docs/challenges/README.md via ``mu reflect``. The per-problem pass-rate table
(printed at the end) shows which problems fail chronically — those are reflex
candidates. TODO.md tracks the improvement backlog.

    python -m mu.dojo practice                      # 100 rounds
    ROUNDS=10 python -m mu.dojo practice
    STOP_AFTER_BARREN=3 python -m mu.dojo practice   # bail after N no-success rounds
    SKIP_REFLECT=1 SKIP_AUTOCOMMIT=1 python -m mu.dojo practice

Every optional step (warm, the round, reflect, token-report, autocommit) is
best-effort: a single failure must never abort a long multi-round run.
"""

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from . import readme, sessions
from .env import augment_path, lmstudio_host, mu_cmd
from .sessions import SessionMeta

@contextlib.contextmanager
def _best_effort(label: str):
    """Run an optional step; log and swallow any failure. This is the ``|| true``
    the scripts relied on — one failed reflect must not kill a 100-round run."""
    try:
        yield
    except Exception as e:  # noqa: BLE001 — deliberately broad: keep the loop alive
        print(f"  ({label} skipped: {e})", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Preconditions
# --------------------------------------------------------------------------- #
def _acquire_lock() -> object:
    """Single-instance lock so two practice runs can't race on the dojo dir or
    the archive. fcntl.flock, with a graceful skip where unavailable."""
    lockfile = os.environ.get('PRACTICE_LOCK') or f"/tmp/practice-{os.getuid()}.lock"
    fh = open(lockfile, 'w')
    try:
        import fcntl
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        print("practice: flock not available; concurrency lock disabled", file=sys.stderr)
    except OSError:
        sys.exit(f"practice: another practice run is already holding {lockfile}")
    return fh


def _preflight_ok() -> bool:
    """Confirm LM Studio is reachable; a round against a dead endpoint burns one
    session per problem with no learning signal."""
    if os.environ.get('SKIP_PREFLIGHT'):
        return True
    import urllib.request
    host = lmstudio_host()
    try:
        urllib.request.urlopen(f"{host}/v1/models", timeout=5)
        return True
    except Exception:
        print(f"practice: LM Studio not reachable at {host}", file=sys.stderr)
        print("  start it and load a model, or re-run with SKIP_PREFLIGHT=1", file=sys.stderr)
        return False


# --------------------------------------------------------------------------- #
# Post-round learning (all best-effort)
# --------------------------------------------------------------------------- #
def _reflect(fails: list[SessionMeta]) -> None:
    if not fails or os.environ.get('SKIP_REFLECT'):
        return
    limit = os.environ.get('REFLECT_LIMIT', '10')
    ids = [s.session_id for s in fails if s.session_id and s.session_id != '?']
    with _best_effort('reflect'):
        subprocess.run(mu_cmd() + ['reflect', '-n', limit, *ids], check=False)


def _token_report() -> None:
    with _best_effort('token-report'):
        subprocess.run(mu_cmd() + ['token-report', '--output', 'token_usage.md'], check=False)


def _git_dirty(path: str) -> bool:
    return subprocess.run(['git', 'diff-index', '--quiet', 'HEAD', '--', path]).returncode != 0


def _git_tracked(path: str) -> bool:
    return subprocess.run(['git', 'ls-files', '--error-unmatch', path],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _autocommit(round_num: int) -> None:
    if os.environ.get('SKIP_AUTOCOMMIT'):
        return
    if subprocess.run(['git', 'rev-parse', '--git-dir'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        return
    with _best_effort('autocommit'):
        files = []
        if Path('docs/challenges/README.md').is_file() and _git_dirty('docs/challenges/README.md'):
            files.append('docs/challenges/README.md')
        if Path('token_usage.md').is_file() and (not _git_tracked('token_usage.md') or _git_dirty('token_usage.md')):
            subprocess.run(['git', 'add', 'token_usage.md'])
            files.append('token_usage.md')
        index = 'docs/problems/README.md'
        if Path(index).is_file() and _git_dirty(index):
            files.append(index)
        if not files:
            return
        ver = _mu_version()
        subprocess.run(['git', 'commit', '-o', *files, '-m',
                        f"dojo round {round_num}: update problem index, "
                        f"docs/challenges/README.md, token_usage.md (mu {ver})"],
                       stdout=subprocess.DEVNULL)


def _mu_version() -> str:
    try:
        from mu import __version__
        return __version__
    except Exception:
        return '?'


# --------------------------------------------------------------------------- #
# Final per-problem summary
# --------------------------------------------------------------------------- #
def _pass_rate_summary(all_sessions: list[SessionMeta]) -> str:
    """Per-problem pass rate across the whole practice run, worst first. A
    problem that fails round after round is a chronic general-class error; one
    that's stochastic is closer to the model ceiling."""
    tot = Counter(s.problem_id for s in all_sessions)
    ok = Counter(s.problem_id for s in all_sessions if s.passed)
    lines = []
    for pid in sorted(tot, key=lambda p: ok[p] / tot[p]):
        pct = int(ok[pid] / tot[pid] * 100 + 0.5)
        lines.append(f"- {pid:<16} {ok[pid]}/{tot[pid]} passed ({pct}%)")
    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    """Signal the round's whole process group; fall back to the child alone."""
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(OSError):
            proc.send_signal(sig)


def run() -> int:
    augment_path()
    os.environ['MU_ENRICH_LESSONS'] = '1'
    rounds = int(os.environ.get('ROUNDS', '100'))
    stop_after_barren = int(os.environ.get('STOP_AFTER_BARREN', '5'))
    round_timeout = int(os.environ.get('ROUND_TIMEOUT', '1800'))

    _acquire_lock()  # held for the life of the process
    if not _preflight_ok():
        return 1

    print("Warming up the model…")
    with _best_effort('warm'):
        subprocess.run(mu_cmd() + ['model', 'warm'], check=False)

    all_sessions: list[SessionMeta] = []
    total_ok = total_fail = 0
    barren = empty = 0
    started = time.time()
    last_round = 0

    for round_num in range(1, rounds + 1):
        last_round = round_num
        round_start = time.time()
        print(f"\n=== round {round_num}/{rounds} ===")

        marker = sessions.now()
        with _best_effort('round'):
            # The round runs in its own process group: the agent is a
            # *grand*child (run → mu agent), so signalling only the direct
            # child orphans the agent — run 5 left a `mu agent` grinding on
            # p10 for 10+ minutes after the collection window closed,
            # leaving 4 unfinalized sessions. SIGTERM the whole group first
            # so the in-flight mu session can finalize its archive (outcome
            # 'interrupted'); SIGKILL the group only if it doesn't exit.
            proc = subprocess.Popen([sys.executable, '-m', 'mu.dojo', 'run'],
                                    start_new_session=True)
            try:
                proc.wait(timeout=round_timeout)
            except subprocess.TimeoutExpired:
                _signal_group(proc, signal.SIGTERM)
                try:
                    proc.wait(timeout=30)
                    print(f"round {round_num}: exceeded {round_timeout}s — terminated",
                          file=sys.stderr)
                except subprocess.TimeoutExpired:
                    _signal_group(proc, signal.SIGKILL)
                    proc.wait()
                    print(f"round {round_num}: exceeded {round_timeout}s — killed",
                          file=sys.stderr)

        round_sessions = sessions.sessions_since(marker)
        fails = [s for s in round_sessions if not s.passed]
        successes = len(round_sessions) - len(fails)
        all_sessions.extend(round_sessions)

        with _best_effort('readme'):
            readme.refresh(round_sessions, round_num)

        total_ok += successes
        total_fail += len(fails)
        elapsed = int(time.time() - round_start)
        print(f"round {round_num}: {successes} ok / {len(fails)} fail ({elapsed}s)"
              f"  | cumulative {total_ok} ok / {total_fail} fail")

        _reflect(fails)
        _token_report()
        _autocommit(round_num)

        # Barren = no successes; empty = no sessions at all (LM Studio died or
        # the timeout fired). Both reset on any success; two empty in a row bails.
        if successes > 0:
            barren = empty = 0
        else:
            barren += 1
            if not fails:
                empty += 1
                print(f"round {round_num}: empty (no sessions finalized) — counted as barren")
                if empty >= 2:
                    print("two empty rounds in a row — bailing")
                    break
            else:
                empty = 0
            if barren >= stop_after_barren:
                print(f"no successes for {barren} rounds — bailing out so a human can look")
                break

        print("mu!...")

    total_elapsed = int(time.time() - started)
    print(f"\npractice complete: {total_ok} ok / {total_fail} fail across "
          f"{last_round} round(s) in {total_elapsed}s")

    if all_sessions:
        summary = _pass_rate_summary(all_sessions)
        print(f"\nper-problem pass rate (worst first):\n{summary}")
    return 0
