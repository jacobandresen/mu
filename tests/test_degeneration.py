"""Tests for the degeneration guard (mu.degeneration.is_degenerate).

The negatives matter more than the positives: a false positive on legitimately
repetitive code regresses every run. So the bulk of this file asserts that
normal source — indentation, repeated `self.`, big literals, many blank lines —
is *not* flagged, and only true back-to-back token loops are.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mu.degeneration import is_degenerate, guard_enabled  # noqa: E402


# ── Positives: genuine degeneration must be caught ────────────────────────────

def test_intra_line_token_loop():
    # The canonical failure: a short fragment repeated with no newlines.
    assert is_degenerate('print(f"{task[' * 200)


def test_repeated_line_loop():
    # A whole line emitted over and over.
    assert is_degenerate('x = compute(x)\n' * 200)


def test_multiline_block_loop():
    # A two-line block repeated forever (period includes the newline).
    assert is_degenerate('def f():\n    return f()\n' * 100)


def test_loop_dominating_a_valid_prefix():
    # Some valid code, then a loop that takes over the majority of the file.
    prefix = "def main():\n    print('ok')\n    return 0\n"
    assert is_degenerate(prefix + 'AB' * 4000)


def test_single_char_runaway():
    assert is_degenerate('a' * 5000)


# ── Negatives: normal source must never be flagged ────────────────────────────

def test_normal_python_module_not_flagged():
    src = (
        "import json\n"
        "from pathlib import Path\n\n"
        "class TodoManager:\n"
        "    def __init__(self, db_path):\n"
        "        self.db_path = db_path\n"
        "        self.conn = None\n\n"
        "    def add(self, task):\n"
        "        self.tasks.append(task)\n"
        "        return len(self.tasks)\n\n"
        "    def remove(self, task):\n"
        "        self.tasks.remove(task)\n"
        "        return len(self.tasks)\n"
    ) * 4  # a few hundred chars of perfectly ordinary, repetitive-looking code
    assert not is_degenerate(src)


def test_deep_indentation_not_flagged():
    # Many lines starting with the same whitespace — distant repetition, legit.
    src = '\n'.join('    ' * 4 + f'value_{i} = compute({i})' for i in range(80))
    assert not is_degenerate(src)


def test_repeated_self_assignments_not_flagged():
    # `self.x = x` over and over with different names — looks repetitive, isn't a loop.
    src = '\n'.join(f'        self.field_{i} = field_{i}' for i in range(60))
    assert not is_degenerate(src)


def test_large_dict_literal_not_flagged():
    # A wide literal: structurally periodic-looking but every entry differs.
    body = ',\n'.join(f'    "key_{i}": {i * 7}' for i in range(120))
    assert not is_degenerate('DATA = {\n' + body + '\n}\n')


def test_many_blank_lines_not_flagged():
    # A whitespace run is not a corrupting loop.
    assert not is_degenerate('def f():\n    pass\n' + '\n' * 400)


def test_nested_closing_not_flagged():
    # Deeply nested code closes with braces at *different* indentation — the lines
    # differ, so there's no back-to-back identical run.
    closes = '\n'.join('    ' * d + '}' for d in range(8, 0, -1))
    src = ('def handler():\n    data = {\n        "a": {\n' + closes + '\n') * 6
    assert not is_degenerate(src)


def test_short_output_not_judged():
    # Too short to be confident — never flagged.
    assert not is_degenerate('ab' * 20)


# ── Toggle ────────────────────────────────────────────────────────────────────

def test_guard_enabled_default(monkeypatch=None):
    os.environ.pop('MU_DEGEN_GUARD', None)
    assert guard_enabled() is True
    os.environ['MU_DEGEN_GUARD'] = '0'
    try:
        assert guard_enabled() is False
    finally:
        os.environ.pop('MU_DEGEN_GUARD', None)


if __name__ == '__main__':
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
