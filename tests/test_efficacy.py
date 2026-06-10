"""Tests for efficacy storage and the §5z gate (no LLM required).

docs/REFLEX_KB.md §5z: a reflex's efficacy is accepted only when the 95% CI
of per-seed Δ values excludes 0 across ≥3 seeds. sz5_gate() encodes this
predicate; it is reused by iter-5's test_ablation_rule.py.
"""

import pytest
from mu.reflexdb import connect, record_efficacy, sz5_gate, build


# ─── §5z gate ────────────────────────────────────────────────────────────────

def test_sz5_gate_positive_effect():
    # Clear positive Δ (disabled → better) — CI excludes 0 from above
    assert sz5_gate([0.3, 0.35, 0.4]) is True


def test_sz5_gate_negative_effect():
    # Clear negative Δ (reflex helped) — CI excludes 0 from below
    assert sz5_gate([-0.3, -0.35, -0.4]) is True


def test_sz5_gate_requires_3_seeds():
    assert sz5_gate([0.5, 0.5]) is False
    assert sz5_gate([]) is False
    assert sz5_gate([0.5]) is False


def test_sz5_gate_ci_spans_zero():
    # Mixed-sign deltas — CI contains 0, gate should reject
    assert sz5_gate([0.2, -0.1, 0.05, -0.15, 0.1]) is False


def test_sz5_gate_all_zero():
    # All zeros — no effect at all
    assert sz5_gate([0.0, 0.0, 0.0]) is False


def test_sz5_gate_exactly_3_seeds():
    # Boundary: exactly 3 seeds with consistent direction
    assert sz5_gate([-0.4, -0.5, -0.45]) is True


# ─── record_efficacy write / read-back ───────────────────────────────────────

@pytest.fixture
def test_db(tmp_path):
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    db = str(tmp_path / 'test.db')
    build(db_path=db, sessions_dir=str(sessions_dir))
    return db


def test_record_efficacy_stores_runs(test_db):
    rid = 'fix_json_unclosed_brackets'  # known in the catalog
    record_efficacy(rid, 'seed42', baseline_hits=4, baseline_n=5,
                    disabled_hits=1, disabled_n=5, db_path=test_db)
    con = connect(test_db)
    rows = con.execute("SELECT * FROM efficacy_run WHERE reflex_id=?", (rid,)).fetchall()
    assert len(rows) == 1
    assert rows[0]['delta'] == pytest.approx(1/5 - 4/5)  # 0.2 - 0.8 = -0.6
    con.close()


def test_record_efficacy_sets_efficacy_after_3_seeds(test_db):
    rid = 'fix_json_unclosed_brackets'
    # Seed the three runs that all show the reflex helped
    record_efficacy(rid, 'seed0',  baseline_hits=4, baseline_n=5,
                    disabled_hits=1, disabled_n=5, db_path=test_db)
    record_efficacy(rid, 'seed42', baseline_hits=3, baseline_n=5,
                    disabled_hits=1, disabled_n=5, db_path=test_db)
    # reflex.efficacy still NULL after only 2 seeds
    con = connect(test_db)
    row = con.execute("SELECT efficacy FROM reflex WHERE id=?", (rid,)).fetchone()
    assert row['efficacy'] is None
    con.close()

    record_efficacy(rid, 'seed7',  baseline_hits=4, baseline_n=5,
                    disabled_hits=2, disabled_n=5, db_path=test_db)
    # Now ≥3 seeds — efficacy should be the mean Δ
    con = connect(test_db)
    row = con.execute("SELECT efficacy FROM reflex WHERE id=?", (rid,)).fetchone()
    assert row['efficacy'] is not None
    assert row['efficacy'] < 0, "mean Δ should be negative (reflex helped)"
    con.close()


def test_record_efficacy_delta_direction(test_db):
    """disabled_pass_rate > baseline means reflex was net-negative (positive Δ)."""
    rid = 'fix_no_targets'
    for seed in ('s1', 's2', 's3'):
        # Disabling the reflex improved things (disabled 5/5, baseline 2/5)
        record_efficacy(rid, seed, baseline_hits=2, baseline_n=5,
                        disabled_hits=5, disabled_n=5, db_path=test_db)
    con = connect(test_db)
    row = con.execute("SELECT efficacy FROM reflex WHERE id=?", (rid,)).fetchone()
    assert row['efficacy'] > 0, "positive Δ when disabling helped"
    con.close()


def test_efficacy_survives_rebuild(test_db, tmp_path):
    """record_efficacy data must not be wiped by a subsequent build()."""
    rid = 'fix_json_unclosed_brackets'
    for seed in ('a', 'b', 'c'):
        record_efficacy(rid, seed, baseline_hits=4, baseline_n=5,
                        disabled_hits=1, disabled_n=5, db_path=test_db)

    sessions_dir = tmp_path / 'sessions'
    build(db_path=test_db, sessions_dir=str(sessions_dir))

    con = connect(test_db)
    runs = con.execute("SELECT COUNT(*) c FROM efficacy_run WHERE reflex_id=?",
                       (rid,)).fetchone()['c']
    eff = con.execute("SELECT efficacy FROM reflex WHERE id=?",
                      (rid,)).fetchone()['efficacy']
    con.close()
    assert runs == 3, "efficacy_run rows must survive rebuild"
    assert eff is not None, "reflex.efficacy must be restored after rebuild"
