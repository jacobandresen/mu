"""Tests for repair-loop context helpers: test output extraction and windowing."""

import tempfile
from pathlib import Path

import pytest

from mu.agent import _error_lines_for_file, _extract_test_failures, _file_block


# ── _extract_test_failures ────────────────────────────────────────────────────

PYTEST_OUTPUT = """\
============================= test session starts ==============================
platform darwin -- Python 3.11.9
collected 2 items

tests/test_app.py::test_create FAILED                                    [ 50%]
tests/test_app.py::test_read   FAILED                                    [100%]

=================================== FAILURES ===================================
_____________________________ test_create ______________________________

    def test_create(client):
>       r = client.post('/todos', json={'title': 'buy milk'})

E       AssertionError: assert 500 == 201

tests/test_app.py:12: AssertionError
=========================== short test summary info ============================
FAILED tests/test_app.py::test_create
FAILED tests/test_app.py::test_read
2 failed in 0.34s
"""

PYTEST_ERRORS_OUTPUT = """\
============================= test session starts ==============================
collected 0 items / 1 error

=================================== ERRORS ====================================
______________ ERROR collecting tests/test_app.py _______________
ImportError while importing: No module named 'app'
1 error in 0.08s
"""

JEST_OUTPUT = """\
 FAIL tests/todo.test.js
  Todo
    ✓ list (4ms)
    ✗ create (12ms)

  ● Todo › create

    expect(received).toBe(expected)
    Expected: 201
    Received: 500

      at tests/todo.test.js:15:5

Test Suites: 1 failed, 1 total
"""

CARGO_OUTPUT = """\
running 3 tests
test fib_0 ... ok
test fib_1 ... ok
test fib_10 ... FAILED

failures:

---- fib_10 stdout ----
thread 'fib_10' panicked at 'assertion `left == right` failed'

test result: FAILED. 2 passed; 1 failed
"""

PASSING_OUTPUT = """\
============================= test session starts ==============================
collected 3 items

tests/test_app.py::test_ping PASSED                                      [100%]

1 passed in 0.12s
"""


def _write_log(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False)
    f.write(content)
    f.close()
    return f.name


def test_extract_pytest_failures():
    path = _write_log(PYTEST_OUTPUT)
    result = _extract_test_failures(path)
    Path(path).unlink()
    assert 'FAILURES' in result
    assert 'AssertionError' in result
    assert 'test session starts' not in result  # header stripped


def test_extract_pytest_errors():
    path = _write_log(PYTEST_ERRORS_OUTPUT)
    result = _extract_test_failures(path)
    Path(path).unlink()
    assert 'ERRORS' in result
    assert "No module named 'app'" in result


def test_extract_jest():
    path = _write_log(JEST_OUTPUT)
    result = _extract_test_failures(path)
    Path(path).unlink()
    assert '● Todo' in result
    assert 'Expected: 201' in result
    # jest header before the bullet should be stripped
    assert 'FAIL tests/todo.test.js' not in result


def test_extract_cargo():
    path = _write_log(CARGO_OUTPUT)
    result = _extract_test_failures(path)
    Path(path).unlink()
    assert 'failures:' in result
    assert 'fib_10' in result
    assert 'running 3 tests' not in result


def test_extract_fallback_to_tail_on_passing():
    path = _write_log(PASSING_OUTPUT)
    result = _extract_test_failures(path)
    Path(path).unlink()
    # No failure block — should fall back and include the summary line
    assert '1 passed' in result


def test_extract_empty_log():
    path = _write_log('')
    result = _extract_test_failures(path)
    Path(path).unlink()
    assert result == ''


def test_extract_missing_file():
    result = _extract_test_failures('/nonexistent/path.log')
    assert result == ''


def test_extract_max_chars():
    long_failures = '================================= FAILURES =================================\n' + ('E   assert x == y\n' * 300)
    path = _write_log(long_failures)
    result = _extract_test_failures(path, max_chars=500)
    Path(path).unlink()
    assert len(result) <= 520  # max_chars + truncation marker overhead
    assert '[truncated]' in result


# ── _error_lines_for_file ─────────────────────────────────────────────────────

def test_error_lines_basic():
    lines = _error_lines_for_file('app.py', 'app.py:42: AssertionError')
    assert lines == [42]


def test_error_lines_multiple():
    output = 'app.py:10: error\napp.py:20: error\napp.py:10: again'
    lines = _error_lines_for_file('app.py', output)
    assert lines == [10, 20]  # deduped and sorted


def test_error_lines_no_match():
    lines = _error_lines_for_file('app.py', 'other.py:42: error')
    assert lines == []


def test_error_lines_ignores_zero():
    lines = _error_lines_for_file('app.py', 'app.py:0: error')
    assert lines == []


# ── _file_block (windowing) ────────────────────────────────────────────────────

def _write_py(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp')
    f.write(content)
    f.close()
    return f.name


def test_file_block_no_error_truncates_head():
    # Large file, no error reference — head-truncated
    body = '\n'.join(f'x = {i}' for i in range(1000))
    path = _write_py(body)
    block = _file_block(path, 'unrelated test output', per_file=200)
    Path(path).unlink()
    assert '[truncated]' in block
    assert len(block) <= 250


def test_file_block_with_error_windows_to_function():
    lines = ['import os', '']
    for i in range(30):
        lines += [f'def helper_{i}():', f'    return {i}', '']
    lines += [
        'def target_fn():',
        '    x = broken_call()',
        '    return x',
    ]
    body = '\n'.join(lines)
    path = _write_py(body)
    basename = Path(path).name
    err_line = len(lines)  # last line
    test_out = f'{basename}:{err_line}: NameError'
    block = _file_block(path, test_out, per_file=2500)
    Path(path).unlink()
    # Should contain the target function, not the helpers
    assert 'def target_fn' in block
    assert f'error at {err_line}' in block
    # Should NOT include the large helper section (not enough budget consumed)
    assert 'helper_0' not in block


def test_file_block_fallback_on_missing_file():
    block = _file_block('/nonexistent/file.py', '', per_file=2500)
    assert block == ''
