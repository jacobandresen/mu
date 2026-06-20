"""The capability model (src/mu/capability.py): chain solve-prob, bottleneck,
marginal gain, the whole-set objective E[#solved], and the portfolio selector.
"""
import math

from mu.capability import (LayerStat, bottleneck, e_solved, expected_solve_gain,
                           p_solve, portfolio_gain, rank_portfolio, route)


def _full(n=20):       # a near-certain layer
    return LayerStat(clears=n, n=n)


def _half(n=20):       # a 50/50 layer
    return LayerStat(clears=n // 2, n=n)


def _none(n=20):       # an all-failing layer
    return LayerStat(clears=0, n=n)


def test_q_is_smoothed_rate():
    # Beta-Binomial shrinks toward 0.5, so a perfect layer is high but < 1.
    q = _full().q
    assert 0.9 < q < 1.0
    assert math.isclose(_half().q, 0.5, abs_tol=1e-9)


def test_p_solve_is_the_product():
    layers = {'a': _full(), 'b': _half()}
    assert math.isclose(p_solve(layers), layers['a'].q * layers['b'].q)
    assert p_solve({}) == 1.0


def test_bottleneck_is_argmin_q():
    layers = {'build': _full(), 'test': _none(), 'lint': _half()}
    assert bottleneck(layers) == 'test'
    assert bottleneck({}) is None


def test_expected_gain_zero_when_a_sibling_is_zero():
    # All-failing problem: lifting one layer buys ~nothing (a sibling pins it).
    layers = {'a': _none(), 'b': _none()}
    assert expected_solve_gain(layers, 'a', dq=0.3) < 0.05
    # Same lift when the sibling is solid is worth far more.
    layers2 = {'a': _half(), 'b': _full()}
    assert expected_solve_gain(layers2, 'a', dq=0.3) > 0.2


def test_route_skips_hopeless_problem():
    assert route({'a': _none(), 'b': _none()}) is True
    assert route({'a': _full(), 'b': _full()}) is False


def test_e_solved_sums_problem_solve_probs():
    board = {'p1': {'x': _full()}, 'p10': {'a': _none(), 'b': _none()}}
    assert math.isclose(e_solved(board), p_solve(board['p1']) + p_solve(board['p10']))


def test_portfolio_gain_sums_across_covered_problems():
    board = {'p4': {'x': _half()}, 'p10': {'a': _half(), 'b': _full()}}
    broad = portfolio_gain(board, [('p4', 'x'), ('p10', 'a')], beta=0.5)
    narrow = portfolio_gain(board, [('p10', 'a')], beta=0.5)
    assert broad > narrow > 0          # breadth wins


def test_rank_portfolio_prefers_the_broad_steep_step():
    board = {
        'p4':  {'x': _half()},          # steep, headroom
        'p8':  {'x': _half()},          # steep, headroom
        'p10': {'a': _none(), 'b': _none()},   # all-failing, tiny gain
    }
    candidates = [
        ('broad',     [('p4', 'x'), ('p8', 'x')], 0.5, 1.0),   # helps two steep ones
        ('p10_only',  [('p10', 'a')],             0.5, 1.0),   # the hardest, near-0 gain
    ]
    ranked = rank_portfolio(board, candidates)
    assert ranked[0][1] == 'broad'
    assert ranked[-1][1] == 'p10_only'
