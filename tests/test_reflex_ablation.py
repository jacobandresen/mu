"""Ablation hook: MU_DISABLE_REFLEX switches off exactly the named reflex(es).

This is the deterministic core of the causal arbiter (docs/REFLEX_KB.md §9) — no
model needed, so it runs in CI. Two trivial, idempotent fixers append a marker to
a file; we assert which ones fire with the env var set or clear.

Run: `pytest tests/` or `python tests/test_reflex_ablation.py`.
"""

import os
from pathlib import Path

from mu.reflexes.core import (disabled_reflexes, get_firings, reset_firings,
                              run_reflexes)


def fix_marker_a(target: str) -> None:
    """Idempotent: append 'AAA' once."""
    p = Path(target)
    text = p.read_text()
    if 'AAA' not in text:
        p.write_text(text + 'AAA')


def fix_marker_b(target: str) -> None:
    """Idempotent: append 'BBB' once."""
    p = Path(target)
    text = p.read_text()
    if 'BBB' not in text:
        p.write_text(text + 'BBB')


def _run(tmp_path, disable=None):
    """Run both fixers over a fresh file; return (file_text, fired_reflex_ids)."""
    target = tmp_path / 'work.txt'
    target.write_text('seed')
    reset_firings()
    prev = os.environ.get('MU_DISABLE_REFLEX')
    if disable is not None:
        os.environ['MU_DISABLE_REFLEX'] = disable
    else:
        os.environ.pop('MU_DISABLE_REFLEX', None)
    try:
        run_reflexes([fix_marker_a, fix_marker_b], str(target))
    finally:
        if prev is None:
            os.environ.pop('MU_DISABLE_REFLEX', None)
        else:
            os.environ['MU_DISABLE_REFLEX'] = prev
    fired = {f['reflex_id'] for f in get_firings()}
    return target.read_text(), fired


def test_no_disable_runs_both(tmp_path):
    text, fired = _run(tmp_path)
    assert 'AAA' in text and 'BBB' in text
    assert fired == {'fix_marker_a', 'fix_marker_b'}


def test_disable_skips_exactly_that_reflex(tmp_path):
    text, fired = _run(tmp_path, disable='fix_marker_a')
    assert 'AAA' not in text          # disabled one never ran
    assert 'BBB' in text              # the other still did
    assert fired == {'fix_marker_b'}  # and only it is recorded as fired


def test_disable_multiple(tmp_path):
    text, fired = _run(tmp_path, disable='fix_marker_a, fix_marker_b')
    assert text == 'seed'             # both off — file untouched
    assert fired == set()


def test_disabled_reflexes_parses_env():
    prev = os.environ.get('MU_DISABLE_REFLEX')
    os.environ['MU_DISABLE_REFLEX'] = ' a , b ,'  # whitespace + trailing comma
    try:
        assert disabled_reflexes() == {'a', 'b'}
    finally:
        if prev is None:
            os.environ.pop('MU_DISABLE_REFLEX', None)
        else:
            os.environ['MU_DISABLE_REFLEX'] = prev


def test_empty_env_is_noop():
    prev = os.environ.get('MU_DISABLE_REFLEX')
    os.environ.pop('MU_DISABLE_REFLEX', None)
    try:
        assert disabled_reflexes() == set()
    finally:
        if prev is not None:
            os.environ['MU_DISABLE_REFLEX'] = prev


if __name__ == '__main__':  # standalone runner (no pytest needed)
    import tempfile
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith('test_') or not callable(fn):
            continue
        try:
            if 'tmp_path' in fn.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"ok   {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
