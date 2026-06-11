"""Interaction model: Bayesian network over co-occurrence and sequence data.

docs/REFLEX_KB.md §11: a pgmpy Bayesian network over the co-occurrence and
sequence edges recorded in the `firing` table. Strictly observational/offline —
never feeds the runtime runner or predict.py (§10 leak guard).
"""

from pgmpy.models import DiscreteBayesianNetwork


def build_net(con):
    """Build a Bayesian network from firing co-occurrence data.

    Returns a pgmpy.models.DiscreteBayesianNetwork instance, or None when
    there is not enough co-occurrence data (need ≥3 co-occurrences per edge).

    The network is observational — edges represent co-firing, not causation.
    §10 leak guard: must never be called from agent.py or predict.py.
    """
    rows = con.execute(
        "SELECT a.reflex_id x, b.reflex_id y, COUNT(DISTINCT a.session_id) n "
        "FROM firing a JOIN firing b "
        "  ON a.session_id=b.session_id AND a.reflex_id < b.reflex_id "
        "GROUP BY 1,2 ORDER BY n DESC LIMIT 20").fetchall()

    edges = [(r['x'], r['y']) for r in rows if r['n'] >= 3]
    if not edges:
        return None

    return DiscreteBayesianNetwork(edges)
