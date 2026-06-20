"""Step 0.2 — the whole-set board: per-problem layers, p10 log parsing, and the
capability-board aggregation. Tests parse exact per-layer booleans from fixture
logs (a missing/garbled log reads as "not cleared", never a crash) and check the
board's self-consistency wiring.
"""
from mu import capability
from mu.dojo.measure import (_layer_clears, _p10_layer_clears, _problem_layers,
                            _raw_solved)

_P10 = ('backend_build', 'backend_test', 'frontend_build', 'frontend_test')


class _FakeSession:
    def __init__(self, dir=None, outcome="success"):
        self.dir = dir
        self.outcome = outcome


# --- _problem_layers: full-stack declares 4, everything else is a single gate ---

def test_layers_fullstack_vs_trivial():
    assert _problem_layers({"toolchains": ["dotnet", "node"]}) == _P10
    assert _problem_layers({"toolchains": ["c"]}) == ("solved",)
    assert _problem_layers({"toolchains": ["python"]}) == ("solved",)
    assert _problem_layers({}) == ("solved",)


# --- _p10_layer_clears: parse the four gates from staged logs --------------------

def _write_log(tmp_path, text):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "stage.log").write_text(text)
    return tmp_path


def test_p10_all_layers_green(tmp_path):
    d = _write_log(tmp_path, (
        "Build succeeded.\n"
        "Passed!  - Failed:     0, Passed:     3, Total: 3\n"
        "> vite build\ndist/index.html  1.2 kB\n"
        "Test Files  1 passed (1)\n     Tests  2 passed (2)\n"
    ))
    assert _p10_layer_clears(d) == {k: True for k in _P10}


def test_p10_backend_build_error_not_cleared(tmp_path):
    d = _write_log(tmp_path, (
        "Program.cs(3,1): error CS0101: duplicate type\nBuild FAILED.\n"
        "> vite build\nTest Files  1 passed (1)\n"
    ))
    c = _p10_layer_clears(d)
    assert c["backend_build"] is False        # 'error CS' present
    assert c["backend_test"] is False         # no green "Passed! - Failed: 0"
    assert c["frontend_build"] is True


def test_p10_frontend_ts_error_not_cleared(tmp_path):
    d = _write_log(tmp_path, (
        "Build succeeded.\nPassed!  - Failed: 0, Passed: 1\n"
        "> vite build\nsrc/App.vue: error TS2322: type mismatch\n"
    ))
    c = _p10_layer_clears(d)
    assert c["backend_build"] is True
    assert c["frontend_build"] is False       # 'error TS' present
    assert c["frontend_test"] is False        # no "Test Files N passed"


def test_p10_missing_logs_dir_no_crash(tmp_path):
    # no logs/ subdir at all -> every layer reads as not cleared, no exception
    assert _p10_layer_clears(tmp_path) == {k: False for k in _P10}


# --- _layer_clears: single-gate uses outcome; full-stack reads logs -------------

def test_layer_clears_single_gate():
    prob = {"toolchains": ["python"]}
    assert _layer_clears(prob, _FakeSession(outcome="success")) == {"solved": True}
    assert _layer_clears(prob, _FakeSession(outcome="stalled")) == {"solved": False}
    assert _layer_clears(prob, None) == {"solved": False}


def test_layer_clears_fullstack_uses_logs(tmp_path):
    prob = {"toolchains": ["dotnet", "node"]}
    d = _write_log(tmp_path, "Build succeeded.\nPassed!  - Failed: 0\n"
                             "> vite build\nTest Files  1 passed\n")
    c = _layer_clears(prob, _FakeSession(dir=d))
    assert c == {k: True for k in _P10}
    # a missing session => all four layers not cleared, no crash
    assert _layer_clears(prob, None) == {k: False for k in _P10}


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


def test_board_p10_chain_is_product():
    layers = {l: capability.LayerStat(clears=0, n=10) for l in _P10}  # all-failing
    assert capability.p_solve(layers) < 0.5         # chain of low layers ~ 0
    assert capability.bottleneck(layers) in _P10


def test_raw_solved_reconstructs_observed_not_smoothed():
    # the L0 board shape (3b): only p1 solved 4/5, everything else 0 -> raw == 0.8,
    # while the smoothed e_solved is biased high by the uniform prior over 9 zeros.
    board = {
        "p1": {"solved": capability.LayerStat(4, 5)},
        **{f"p{i}": {"solved": capability.LayerStat(0, 5)} for i in range(2, 10)},
        "p10": {l: capability.LayerStat(0, 5) for l in _P10},
    }
    assert abs(_raw_solved(board) - 0.8) < 1e-9          # matches observed solved
    assert capability.e_solved(board) > _raw_solved(board)  # smoothing is biased high
