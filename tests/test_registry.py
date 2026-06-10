"""Registry completeness + schema invariants (docs/REFLEX_KB.md §3, §11).

Deterministic, no model. These pin the contracts the KB depends on: every reflex is
cataloged (so a new one can't be added without classifying it), each has a one-line
summary, and the derived fields use the controlled vocabulary.

Run: `pytest tests/` or `python tests/test_registry.py`.
"""

import shutil
import tempfile
from pathlib import Path

from mu.reflexes.registry import (PHASE_VOCAB, RISK_VOCAB, _load_idempotent_ids,
                                   discover, unregistered)

_TRIGGERS = {'scan', 'lint-out', 'test-out', 'plan', 'project'}
_SCOPES = {'file', 'project'}


def test_every_reflex_is_cataloged():
    # A public fix_*/apply_* not in _CATALOG fails here — forces classification.
    missing = unregistered()
    assert missing == [], f"reflexes missing from the catalog: {missing}"


def test_every_reflex_has_a_summary():
    records = discover()
    assert records, "discover() returned nothing"
    blank = [r.id for r in records if not r.summary]
    assert blank == [], f"reflexes missing a docstring summary: {blank}"


def test_derived_fields_use_controlled_vocab():
    for r in discover():
        assert r.trigger in _TRIGGERS, f"{r.id}: bad trigger {r.trigger!r}"
        assert r.scope in _SCOPES, f"{r.id}: bad scope {r.scope!r}"


def test_ids_are_unique():
    ids = [r.id for r in discover()]
    assert len(ids) == len(set(ids)), "duplicate reflex ids in the catalog"


def test_new_fields_controlled_vocab():
    """phase and risk use controlled vocabularies; evidence must not be None."""
    for r in discover():
        assert r.phase in PHASE_VOCAB, f"{r.id}: bad phase {r.phase!r}"
        assert r.risk in RISK_VOCAB, f"{r.id}: bad risk {r.risk!r}"
        assert r.evidence is not None, f"{r.id}: evidence must not be None"


def test_idempotent_only_scan_file():
    """Non-scan/file reflexes must have idempotent=None (never measured)."""
    for r in discover():
        if r.trigger != 'scan' or r.scope != 'file':
            assert r.idempotent is None, \
                f"{r.id}: only scan/file reflexes can have idempotent set"


def test_idempotent_ids_committed():
    """idempotent_ids.txt must match the live double-apply measurement.

    Update idempotent_ids.txt if this fails (a new fixture exercised a reflex
    or an existing reflex's behavior changed)."""
    fixture_dir = Path(__file__).with_name('fixtures')
    fixtures = [f for f in fixture_dir.iterdir()
                if f.is_file() and f.stat().st_size > 0] if fixture_dir.exists() else []
    if not fixtures:
        return  # no non-empty fixtures yet

    measured: set[str] = set()
    for rec in discover():
        if rec.trigger != 'scan' or rec.scope != 'file':
            continue
        try:
            mod = __import__(f'mu.reflexes.{rec.toolchain}', fromlist=[rec.id])
            fn = mod.__dict__[rec.id]
        except (ImportError, KeyError):
            continue
        candidate = next(
            (f for f in fixtures if any(k in rec.id for k in f.stem.split('_'))),
            fixtures[0])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / candidate.name
            shutil.copy2(candidate, p)
            before = p.read_bytes()
            try:
                fn(str(p))
            except Exception:
                continue
            after1 = p.read_bytes()
            if after1 == before:
                continue
            try:
                fn(str(p))
            except Exception:
                pass  # exception on second apply is fine — check file state
            after2 = p.read_bytes()
            if after1 == after2:
                measured.add(rec.id)

    committed = _load_idempotent_ids()
    assert measured == committed, (
        f"idempotent_ids.txt is stale.\n"
        f"  measured:  {sorted(measured)}\n"
        f"  committed: {sorted(committed)}\n"
        f"Update src/mu/reflexes/idempotent_ids.txt to fix.")


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
