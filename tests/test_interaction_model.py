"""Interaction model tests (docs/REFLEX_KB.md §11).

The §10 leak guard is structural: build_net() must not be imported from
agent.py or predict.py; tested by inspection.
"""

import sqlite3

import pytest

from mu.interaction import build_net
from mu.reflexdb import _SCHEMA


def _db_with_cofirings():
    """Minimal in-memory DB with enough co-firing data to produce edges."""
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    sessions = [('s' + str(i), 1) for i in range(10)]
    con.executemany("INSERT INTO session(session_id, success) VALUES (?,?)", sessions)
    firings = []
    for i in range(8):
        sid = 's' + str(i)
        firings.extend([(sid, 'R1', 0), (sid, 'R2', 1)])
    for i in range(3):
        sid = 's' + str(i)
        firings.append((sid, 'R3', 2))
    con.executemany("INSERT INTO firing(session_id, reflex_id, pass_index) VALUES (?,?,?)",
                    firings)
    con.commit()
    return con


def _db_sparse():
    """Minimal DB with too few co-firings to meet the ≥3 threshold."""
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    con.executemany("INSERT INTO session(session_id, success) VALUES (?,?)",
                    [('s1', 1), ('s2', 0)])
    con.executemany("INSERT INTO firing(session_id, reflex_id, pass_index) VALUES (?,?,?)",
                    [('s1', 'R1', 0), ('s1', 'R2', 1)])  # only 1 co-occurrence
    con.commit()
    return con


def test_build_net_returns_network():
    net = build_net(_db_with_cofirings())
    assert net is not None


def test_build_net_edges_reflect_cofirings():
    net = build_net(_db_with_cofirings())
    assert net is not None
    nodes = set(net.nodes())
    assert 'R1' in nodes
    assert 'R2' in nodes


def test_build_net_returns_none_when_sparse():
    assert build_net(_db_sparse()) is None


def test_leak_guard_agent_does_not_import_interaction():
    import pathlib
    agent_src = pathlib.Path(__file__).parents[1] / 'src' / 'mu' / 'agent.py'
    text = agent_src.read_text()
    assert 'interaction' not in text, (
        "§10 leak guard: interaction model must not be imported from agent.py")


def test_leak_guard_predict_does_not_import_interaction():
    import pathlib
    predict = pathlib.Path(__file__).parents[1] / 'src' / 'mu' / 'predict.py'
    if not predict.exists():
        pytest.skip('predict.py does not exist')
    text = predict.read_text()
    assert 'interaction' not in text, (
        "§10 leak guard: interaction model must not be imported from predict.py")
