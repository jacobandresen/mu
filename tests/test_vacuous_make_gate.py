"""The test gate must not certify a vacuous make run as a pass.

`make test` against a recipe-less `test:` target exits 0 while printing
"make: Nothing to be done for `test'." — no test ran. Counting that as a pass
inflated p7-flask's score with Flask APIs that were never tested. A make-only
test command that did nothing is a failure; a `make && ./binary` command (p1/p3)
is gated by the binary's own exit code and must be left alone.
"""
from pathlib import Path

from mu.agent import _make_vacuous


def _log(tmp_path, text):
    p = tmp_path / 'tests.log'
    p.write_text(text)
    return str(p)


def test_make_test_nothing_to_be_done_is_vacuous(tmp_path):
    log = _log(tmp_path, "make: Nothing to be done for `test'.\n")
    assert _make_vacuous('make test', log) is True


def test_make_only_chain_nothing_to_be_done_is_vacuous(tmp_path):
    log = _log(tmp_path, "make: Nothing to be done for `test'.\n")
    assert _make_vacuous('make install && make test', log) is True


def test_make_and_run_binary_is_not_flagged(tmp_path):
    """p1/p3: the chained ./binary is the real gate — never flag it vacuous."""
    log = _log(tmp_path, "make: Nothing to be done for `all'.\n")
    assert _make_vacuous('make && ./hello', log) is False
    assert _make_vacuous('make && ./sdl2_line', log) is False


def test_real_test_output_is_not_vacuous(tmp_path):
    log = _log(tmp_path, "collected 1 item\n\ntest_main.py .\n\n1 passed in 0.05s\n")
    assert _make_vacuous('make test', log) is False


def test_non_make_command_never_vacuous(tmp_path):
    log = _log(tmp_path, "make: Nothing to be done for `test'.\n")
    # A pytest/jest command is not a make invocation — out of scope.
    assert _make_vacuous('pytest', log) is False
    assert _make_vacuous('npx jest', log) is False
