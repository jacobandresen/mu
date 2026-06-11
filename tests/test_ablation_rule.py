"""Ablation rule test: sz5_gate() as a reusable decision predicate (§5z).

docs/REFLEX_KB.md §11: test_ablation_rule.py provides a reusable predicate for
ablation decisions. sz5_gate() is the canonical gate — keep a reflex change only
if the 95% CI of per-seed Δ values excludes 0 across ≥3 seeds. This file tests
the gate as a decision rule (keep / revert) and verifies it behaves correctly at
the boundary (exactly 3 seeds, near-zero effect, mixed-sign).

See also test_efficacy.py for lower-level sz5_gate unit tests and DB integration.
"""

import pytest

from mu.reflexdb import sz5_gate


# ── keep decision (effect is real) ───────────────────────────────────────────

def test_keep_when_reflex_clearly_hurts():
    # Disabling the reflex consistently raised the pass rate — positive Δ, gate opens.
    deltas = [0.20, 0.18, 0.22, 0.19, 0.21]
    assert sz5_gate(deltas) is True, "positive uniform Δ should clear the gate"


def test_keep_when_reflex_clearly_helps():
    # Disabling the reflex consistently lowered the pass rate — negative Δ, gate opens.
    deltas = [-0.30, -0.28, -0.32]
    assert sz5_gate(deltas) is True, "negative uniform Δ should clear the gate"


# ── revert decision (no real effect) ─────────────────────────────────────────

def test_revert_when_noisy_mixed_signs():
    # Δ straddles zero — CI includes 0, gate stays closed, keep original order.
    deltas = [0.10, -0.08, 0.05, -0.12, 0.03]
    assert sz5_gate(deltas) is False


def test_revert_when_all_zero():
    assert sz5_gate([0.0, 0.0, 0.0]) is False


def test_revert_when_tiny_mixed_effect():
    # Near-zero with sign variance — CI spans 0, gate stays closed.
    deltas = [0.001, -0.001, 0.002, -0.002, 0.001]
    assert sz5_gate(deltas) is False


# ── boundary: minimum seed count ─────────────────────────────────────────────

def test_revert_below_minimum_seeds():
    assert sz5_gate([0.5, 0.5]) is False
    assert sz5_gate([0.5]) is False
    assert sz5_gate([]) is False


def test_keep_at_exactly_3_seeds_with_strong_effect():
    assert sz5_gate([0.40, 0.45, 0.42]) is True


# ── reusable predicate contract: callable, returns bool ──────────────────────

def test_sz5_gate_is_pure_function():
    deltas = [0.3, 0.35, 0.4]
    result_a = sz5_gate(deltas)
    result_b = sz5_gate(list(deltas))  # new list, same values
    assert result_a == result_b, "sz5_gate must be deterministic (no side effects)"


def test_sz5_gate_returns_bool():
    assert isinstance(sz5_gate([0.3, 0.35, 0.4]), bool)
    assert isinstance(sz5_gate([0.1, -0.1, 0.05]), bool)
