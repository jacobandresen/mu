"""Step 0.1 / S1 — honest per-layer gates for every toolchain.

A test gate that exits 0 but ran no tests is a *vacuous pass* (the p7-flask false
pass). ``agent._vacuous_log`` must catch that for every dojo toolchain, while never
reclassifying a genuine pass (or a genuine failure where tests actually ran). The
Accept criterion is zero false-negatives on real green logs.
"""
import textwrap

import pytest

from mu.agent import _make_vacuous, _vacuous_log, _vacuous_pass


# --- per-toolchain vacuous logs (exit 0, but nothing ran) => flagged --------

VACUOUS = {
    "pytest-collected-0": "platform linux -- Python 3.11\ncollected 0 items\n\nno tests ran in 0.01s\n",
    "pytest-no-tests-ran": "collected 0 items\n========== no tests ran in 0.00s ==========\n",
    "go-no-test-files": "?   \tmodule/pkg\t[no test files]\n?   \tmodule/cmd\t[no test files]\n",
    "go-nothing-to-run": "testing: warning: no tests to run\nPASS\nok\tmodule\t0.001s\n".replace("ok\t", "?? "),
    "cargo-0-tests": "   Compiling blog v0.1.0\n    Finished test\nrunning 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored\n",
    "dotnet-no-test-available": "Build succeeded.\nNo test is available in /app/bin/Blog.dll. Make sure test discovery is configured.\n",
    "dotnet-build-failed": "Determining projects to restore...\n/app/Program.cs(3,1): error CS1002: ; expected\nBuild FAILED.\n",
    "dotnet-total-0": "Starting test execution, please wait...\nPassed!  - Failed:     0, Passed:     0, Skipped:     0, Total tests: 0\n",
    "jest-no-tests-found": "No tests found, exiting with code 0\nPattern: src - 0 matches\n",
    "vitest-no-test-files": "No test files found, exiting with code 0\n",
    "make-nothing": "make: Nothing to be done for 'test'.\n",   # via _make_vacuous
}

# --- genuine green logs (tests really ran and passed) => NOT flagged --------

GENUINE_PASS = {
    "pytest": "collected 3 items\n\ntests/test_x.py ...                          [100%]\n\n3 passed in 0.12s\n",
    "go-ok": "ok  \tmodule/pkg\t0.123s\n",
    "go-mixed": "ok  \tmodule/pkg\t0.123s\n?   \tmodule/cmd\t[no test files]\n",   # some tested, some not
    "cargo": "running 3 tests\ntest a ... ok\ntest b ... ok\ntest c ... ok\n\ntest result: ok. 3 passed; 0 failed\n",
    "dotnet": "Build succeeded.\nStarting test execution...\nPassed!  - Failed:     0, Passed:     5, Skipped:     0, Total tests: 5\n",
    "dotnet-multiproj-mixed": "Passed!  - Failed: 0, Passed: 4, Total tests: 4\nNo test is available in /app/Other.dll.\n",
    "jest": "Tests:       3 passed, 3 total\nTest Suites: 1 passed, 1 total\n",
    "vitest": "Test Files  1 passed (1)\n     Tests  2 passed (2)\n",
}

# --- genuine failures (tests ran, some failed) => NOT vacuous ---------------

GENUINE_FAIL = {
    "pytest": "collected 3 items\n\ntests/test_x.py .F.\n\n1 failed, 2 passed in 0.10s\n",
    "cargo": "running 2 tests\ntest a ... ok\ntest b ... FAILED\n\ntest result: FAILED. 1 passed; 1 failed\n",
    "dotnet": "Build succeeded.\nFailed!  - Failed:     1, Passed:     4, Skipped:     0, Total tests: 5\n",
    "go-fail": "--- FAIL: TestX (0.00s)\nFAIL\nFAIL\tmodule/pkg\t0.2s\n",
    "jest": "Tests:       1 failed, 2 passed, 3 total\n",
}


@pytest.mark.parametrize("name", list(VACUOUS))
def test_vacuous_logs_are_flagged(name):
    out = VACUOUS[name]
    if name == "make-nothing":
        return  # covered by test_make_vacuous; _vacuous_log doesn't see the cmd
    assert _vacuous_log(out) is True, f"{name} should be flagged vacuous"


@pytest.mark.parametrize("name", list(GENUINE_PASS))
def test_genuine_passes_not_flagged(name):
    # The Accept gate: zero genuine passes reclassified as failures.
    assert _vacuous_log(GENUINE_PASS[name]) is False, f"{name} green run must not be flagged"


@pytest.mark.parametrize("name", list(GENUINE_FAIL))
def test_genuine_failures_not_vacuous(name):
    # A real failure ran tests, so it is not "vacuous" — the exit code fails it.
    assert _vacuous_log(GENUINE_FAIL[name]) is False, f"{name} ran tests; not vacuous"


def test_make_vacuous_via_cmd(tmp_path):
    log = tmp_path / "t.log"
    log.write_text("make: Nothing to be done for 'test'.\n")
    assert _make_vacuous("make test", str(log)) is True
    assert _vacuous_pass("make test", str(log)) is True
    # a make that chains a real binary is gated by that binary, not flagged here
    assert _make_vacuous("make && ./hello", str(log)) is False


def test_vacuous_pass_reads_file(tmp_path):
    log = tmp_path / "t.log"
    log.write_text(VACUOUS["cargo-0-tests"])
    assert _vacuous_pass("cargo test", str(log)) is True
    log.write_text(GENUINE_PASS["cargo"])
    assert _vacuous_pass("cargo test", str(log)) is False


def test_missing_log_is_not_vacuous(tmp_path):
    assert _vacuous_pass("pytest", str(tmp_path / "absent.log")) is False
