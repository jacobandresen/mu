"""Calibration test: Beta-Binomial 95% credible intervals achieve ~95% coverage.

docs/REFLEX_KB.md §11: the Beta-Binomial posterior (observe.beta_binomial) must
be well-calibrated — i.e. the 95% CI contains the true rate ~95% of the time
across many simulated experiments. A poorly calibrated estimator produces intervals
that are too narrow (undercoverage) or too wide (overcoverage).

Test approach: simulate 500 Bernoulli experiments at a known true rate, compute
the Beta-Binomial 95% CI each time, count how often it contains the true rate.
Assert coverage is in [0.88, 1.00] — a tolerance band that rejects gross
miscalibration while accepting Beta shrinkage conservatism.
"""

import random

import pytest

from mu.observe import beta_binomial


_N_SIMS = 500
_N_OBS = 20   # observations per simulated experiment
_LO_BAND = 0.88
_HI_BAND = 1.00


def _coverage(true_rate: float, rng: random.Random) -> float:
    covered = 0
    for _ in range(_N_SIMS):
        hits = sum(1 for _ in range(_N_OBS) if rng.random() < true_rate)
        post = beta_binomial(hits, _N_OBS, base_rate=0.5)
        if post.lo <= true_rate <= post.hi:
            covered += 1
    return covered / _N_SIMS


@pytest.mark.parametrize("true_rate", [0.3, 0.5, 0.7])
def test_beta_binomial_coverage(true_rate):
    rng = random.Random(42)
    cov = _coverage(true_rate, rng)
    assert _LO_BAND <= cov <= _HI_BAND, (
        f"p={true_rate}: coverage={cov:.3f} outside [{_LO_BAND}, {_HI_BAND}]"
    )
