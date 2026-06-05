"""Registry completeness + schema invariants (docs/REFLEX_KB.md §3, §11).

Deterministic, no model. These pin the contracts the KB depends on: every reflex is
cataloged (so a new one can't be added without classifying it), each has a one-line
summary, and the derived fields use the controlled vocabulary.

Run: `pytest tests/` or `python tests/test_registry.py`.
"""

from mu.reflexes.registry import discover, unregistered

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
