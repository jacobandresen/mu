"""Honesty audit tests (docs/REFLEX_KB.md §11, AGENTS §0/§2).

honesty_audit() flags reflexes whose firings concentrate in a single problem.
These are observational warnings only — they don't change reflex behavior.
"""

import sqlite3

from mu.reflexdb import _SCHEMA, honesty_audit


def _db(firings_by_problem: dict[str, list[str]], success: dict[str, int] | None = None):
    """Build an in-memory DB. firings_by_problem: {problem_id: [reflex_id, ...]}.
    Each reflex fires once per session (session ids auto-generated)."""
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    session_rows = []
    firing_rows = []
    sid = 0
    for pid, reflexes in firings_by_problem.items():
        for rid in reflexes:
            s = f's{sid}'
            ok = (success or {}).get(s, 1)
            session_rows.append((s, pid, ok))
            firing_rows.append((s, rid, 0))
            sid += 1
    con.executemany("INSERT INTO session(session_id, problem_id, success) VALUES (?,?,?)",
                    session_rows)
    con.executemany("INSERT INTO firing(session_id, reflex_id, pass_index) VALUES (?,?,?)",
                    firing_rows)
    con.commit()
    return con


def test_concentrated_reflex_is_flagged():
    # R1 fires 8× in p1, 0× in any other problem — should be flagged.
    con = _db({'p1': ['R1'] * 8, 'p2': ['R2'] * 5})
    lines = honesty_audit(con)
    assert lines, "concentrated reflex should generate warnings"
    combined = '\n'.join(lines)
    assert 'R1' in combined
    assert 'p1' in combined


def test_distributed_reflex_is_not_flagged():
    # R1 fires evenly across 3 problems — no concentration.
    con = _db({'p1': ['R1'] * 3, 'p2': ['R1'] * 3, 'p3': ['R1'] * 3})
    lines = honesty_audit(con)
    combined = '\n'.join(lines)
    assert 'R1' not in combined


def test_below_min_n_not_flagged():
    # R1 fires only 4× in one problem — below _MIN_N=5, not enough to warn.
    con = _db({'p1': ['R1'] * 4})
    assert honesty_audit(con) == []


def test_empty_firings_returns_empty():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    assert honesty_audit(con) == []


def test_audit_section_header_present_when_flagged():
    con = _db({'p1': ['R1'] * 9, 'p2': ['R1'] * 1})
    lines = honesty_audit(con)
    assert any('Honesty audit' in ln for ln in lines)
    assert any('single-problem' in ln for ln in lines)


def test_null_problem_id_sessions_excluded():
    # Sessions without a problem_id should not count toward concentration.
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    con.executemany("INSERT INTO session(session_id, problem_id, success) VALUES (?,?,?)",
                    [(f's{i}', None, 1) for i in range(10)])
    con.executemany("INSERT INTO firing(session_id, reflex_id, pass_index) VALUES (?,?,?)",
                    [(f's{i}', 'R1', 0) for i in range(10)])
    con.commit()
    assert honesty_audit(con) == []
