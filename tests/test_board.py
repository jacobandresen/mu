"""Step 0.2 — the whole-set board: per-problem layers, p10 log parsing, and the
capability-board aggregation. Tests parse exact per-layer booleans from fixture
logs (a missing/garbled log reads as "not cleared", never a crash) and check the
board's self-consistency wiring.
"""
from mu import capability
from mu.dojo.measure import (_layer_clears, _p15_layer_clears, _problem_layers,
                            _raw_solved)

_P15 = ('prototype', 'refine')


class _FakeSession:
    def __init__(self, dir=None, outcome="success"):
        self.dir = dir
        self.outcome = outcome


# --- _problem_layers: full-stack declares 2 layers, everything else is a single gate ---

def test_layers_fullstack_vs_trivial():
    assert _problem_layers({"toolchains": ["dotnet", "node"]}) == _P15
    assert _problem_layers({"toolchains": ["c"]}) == ("solved",)
    assert _problem_layers({"toolchains": ["python"]}) == ("solved",)
    assert _problem_layers({}) == ("solved",)


# --- _p15_layer_clears: parse the two gates from staged logs --------------------

def _write_log(tmp_path, text):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "stage.log").write_text(text)
    return tmp_path


def test_p15_all_layers_green(tmp_path):
    d = _write_log(tmp_path, (
        "Build succeeded.\n"
        "Passed!  - Failed:     0, Passed:     3, Total: 3\n"
        "> vite build\ndist/index.html  1.2 kB\n"
        "Test Files  1 passed (1)\n"
    ))
    assert _p15_layer_clears(d) == {k: True for k in _P15}


def test_p15_build_error_not_cleared(tmp_path):
    d = _write_log(tmp_path, (
        "Program.cs(3,1): error CS0101: duplicate type\nBuild FAILED.\n"
    ))
    c = _p15_layer_clears(d)
    assert c["prototype"] is False        # 'Build FAILED' or 'error CS' present
    assert c["refine"] is False           # no green "Passed! - Failed: 0"


# --- _layer_clears: single-gate uses outcome; full-stack reads logs -------------

def test_layer_clears_single_gate():
    prob = {"toolchains": ["python"]}
    assert _layer_clears(prob, _FakeSession(outcome="success")) == {"solved": True}
    assert _layer_clears(prob, _FakeSession(outcome="stalled")) == {"solved": False}
    assert _layer_clears(prob, None) == {"solved": False}


def test_layer_clears_fullstack_uses_logs(tmp_path):
    prob = {"toolchains": ["dotnet", "node"]}
    d = _write_log(tmp_path, (
        "Build succeeded.\n"
        "Passed!  - Failed: 0\n"
        "> vite build\n"
        "Test Files  1 passed\n"
    ))
    c = _layer_clears(prob, _FakeSession(dir=d))
    assert c == {k: True for k in _P15}
    # a missing session => both layers not cleared, no crash
    assert _layer_clears(prob, None) == {k: False for k in _P15}


# --- board aggregation: e_solved wiring + single-gate self-consistency ----------

def test_board_self_consistency_single_gate():
    # 4 single-gate problems; p_solve of a 1-layer problem == its q̂.
    board = {
        "p1": {"solved": capability.LayerStat(clears=10, n=10)},
        "p2": {"solved": capability.LayerStat(clears=7, n=10)},
        "p3": {"solved": capability.LayerStat(clears=0, n=10)},
        "p4": {"solved": capability.LayerStat(clears=5, n=10)},
    }
    es = capability.e_solved(board)
    assert es == sum(capability.p_solve(v) for v in board.values())
    # E[#solved] tracks the observed solved count within ~1 over the set
    observed = (10 + 7 + 0 + 5) / 10
    assert abs(es - observed) <= 1.0


def test_board_p15_chain_is_product():
    layers = {l: capability.LayerStat(clears=0, n=10) for l in _P15}  # all-failing
    assert capability.p_solve(layers) < 0.5         # chain of low layers ~ 0
    assert capability.bottleneck(layers) in _P15


def test_raw_solved_reconstructs_observed_not_smoothed():
    # the L0 board shape (3b): only p1 solved 4/5, everything else 0 -> raw == 0.8,
    # while the smoothed e_solved is biased high by the uniform prior over 9 zeros.
    board = {
        "p1": {"solved": capability.LayerStat(4, 5)},
        **{f"p{i}": {"solved": capability.LayerStat(0, 5)} for i in range(2, 10)},
        "p15": {l: capability.LayerStat(0, 5) for l in _P15},
    }
    assert abs(_raw_solved(board) - 0.8) < 1e-9          # matches observed solved
    assert capability.e_solved(board) > _raw_solved(board)  # smoothing is biased high
