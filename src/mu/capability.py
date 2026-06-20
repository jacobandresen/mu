"""Capability model: turn dojo outcomes into the quantities that pick the next step.

The model (docs/plans/p10-minimization.md §2.0). A problem is a *series/chain* of
verifiable layer-gates; it is solved iff every layer clears. Per-layer clear
probability ``q`` is estimated by Beta-Binomial smoothing (``observe.beta_binomial``),
so a problem's solve-prob is the product ``∏ q`` and the whole set's objective is
``E[#solved] = Σ_i p_solve_i``.

From those it reads off everything the dojo improvement loop needs: which layer to
attack next (``bottleneck`` = ``argmin q``), the marginal value of a step
(``expected_solve_gain``, from ``∂P/∂q = ∏ siblings``), whether to even run a
(model, problem) (``route``), and — across the whole set — which candidate step
buys the most solved problems per unit cost (``portfolio_gain`` / ``rank_portfolio``).

Pure and side-effect-free: it reads counts and returns numbers. Honest only if the
test gates reject vacuous passes (a "green" that ran no tests is not a clear).
Nothing in the agent hot path imports this; it is a measurement/decision helper for
``mu dojo`` and the analysis.
"""

import math
from dataclasses import dataclass

from . import observe  # Beta-Binomial Posterior(rate, lo, hi, n)


@dataclass(frozen=True)
class LayerStat:
    """Clears out of attempts for one layer of one problem — the ``q`` estimate."""
    clears: int
    n: int

    @property
    def q(self) -> float:
        """Smoothed pass probability q̂ (Beta-Binomial posterior mean)."""
        return observe.beta_binomial(self.clears, self.n).rate

    @property
    def ci(self) -> tuple[float, float]:
        """95% credible interval for q̂ — lets a gate decide with few runs."""
        p = observe.beta_binomial(self.clears, self.n)
        return (p.lo, p.hi)


# A problem's layers, and the whole board.
Layers = dict[str, LayerStat]          # layer name -> stat
Board = dict[str, Layers]              # problem id -> its layers


def p_solve(layers: Layers) -> float:
    """Chain solve-prob ``∏ q̂`` (series system): the model's P_i. Empty -> 1.0."""
    return math.prod(s.q for s in layers.values()) if layers else 1.0


def bottleneck(layers: Layers) -> str | None:
    """``argmin q̂`` — the layer the next step should target (the chain's weakest
    link). ``None`` for a problem with no layers."""
    return min(layers, key=lambda l: layers[l].q) if layers else None


def expected_solve_gain(layers: Layers, layer: str, dq: float) -> float:
    """Marginal value of a step that lifts ``layer``'s q̂ by ``dq``:
    ``ΔP_solve ≈ dq · ∏_{l'≠layer} q̂``. ≈0 when a *sibling* layer is ≈0 — why a
    fix to one layer of an all-failing problem buys nothing."""
    others = math.prod(s.q for name, s in layers.items() if name != layer)
    return dq * others


def route(layers: Layers, eps: float = 0.02) -> bool:
    """True = skip this (model, problem): ``p_solve < eps``, so a run is just noise.
    The layer-level generalization of ``fixtures.should_skip``."""
    return p_solve(layers) < eps


def e_solved(board: Board) -> float:
    """``E[#solved] = Σ_i p_solve_i`` — the objective the improvement loop raises."""
    return sum(p_solve(layers) for layers in board.values())


def portfolio_gain(board: Board, targets: list[tuple[str, str]], beta: float) -> float:
    """Expected ``ΔE[#solved]`` of a step with strength ``beta`` covering the given
    ``(problem_id, layer)`` pairs: ``Σ expected_solve_gain``. Summed across **all**
    covered problems, so a broad step (helps several) outranks a narrow one."""
    total = 0.0
    for pid, layer in targets:
        layers = board.get(pid)
        if layers and layer in layers:
            dq = beta * (1 - layers[layer].q)      # logistic headroom on that layer
            total += expected_solve_gain(layers, layer, dq)
    return total


def rank_portfolio(
    board: Board,
    candidates: list[tuple[str, list[tuple[str, str]], float, float]],
) -> list[tuple[float, str]]:
    """Rank candidate steps by expected ``ΔE[#solved]`` per unit cost, best first.

    ``candidates`` are ``(name, targets, beta, cost)``. Returns ``(score, name)``
    sorted descending — the whole-set selector the loop uses to choose what to build.
    """
    scored = [
        (portfolio_gain(board, targets, beta) / max(cost, 1e-9), name)
        for name, targets, beta, cost in candidates
    ]
    return sorted(scored, reverse=True)
