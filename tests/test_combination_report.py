"""Combination analysis (docs/REFLEX_KB.md §7) over a synthetic firing table.

Deterministic, no model: build an in-memory DB with known firings and assert the
conditional-success / co-occurrence / sequence output. Run: `pytest tests/` or
`python tests/test_combination_report.py`.
"""

import sqlite3

from mu.reflexdb import _SCHEMA, combination_report


def _db():
    """A KB with 6 sessions (success 1,1,1,1,0,0):
      R1 fires in all 6 (success in 4) → conditional success at n=6
      R2 fires in s1,s2 only (both success) → n=2, insufficient
      In s1,s2 R1 is pass 0 and R2 is pass 1 → R1 co-occurs with R2 (×2) and
      precedes it (×2)."""
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    success = {'s1': 1, 's2': 1, 's3': 1, 's4': 1, 's5': 0, 's6': 0}
    con.executemany("INSERT INTO session(session_id, success) VALUES (?,?)",
                    list(success.items()))
    firings = [('s1', 'R1', 0), ('s1', 'R2', 1),
               ('s2', 'R1', 0), ('s2', 'R2', 1),
               ('s3', 'R1', 0), ('s4', 'R1', 0),
               ('s5', 'R1', 0), ('s6', 'R1', 0)]
    con.executemany("INSERT INTO firing(session_id, reflex_id, pass_index) VALUES (?,?,?)",
                    firings)
    con.commit()
    return con


def test_conditional_success_reports_n():
    text = '\n'.join(combination_report(_db()))
    assert '## Combination analysis' in text
    # R1 fired in 6 sessions → its line carries n=6 (enough to show a rate).
    r1 = next(ln for ln in text.splitlines() if ln.startswith('- `R1`'))
    assert '(n=6)' in r1
    # R2 fired in only 2 → below the n≥5 gate, shows "insufficient data".
    r2 = next(ln for ln in text.splitlines() if ln.startswith('- `R2`'))
    assert 'insufficient data (n=2)' in r2


def test_co_occurrence_and_sequence():
    text = '\n'.join(combination_report(_db()))
    assert '`R1` + `R2`  ×2' in text        # co-fire in s1, s2
    assert '`R1` → `R2`  ×2' in text         # R1 (pass 0) precedes R2 (pass 1)


def test_ablation_shortlist_respects_n_gate():
    text = '\n'.join(combination_report(_db()))
    assert '### Ablation shortlist' in text
    assert '`R1` (fired in 6 sessions)' in text   # n=6, effect ≈ base → listed
    assert '`R2` (fired in' not in text           # n=2 below the n≥5 gate


def test_empty_firing_is_empty():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    assert combination_report(con) == []


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
