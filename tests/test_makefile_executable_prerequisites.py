"""Tests for fix_makefile_executable_prerequisites: removes executable names used
as Makefile prerequisites (e.g. `venv: pip`, `test: pytestmain`)."""
import textwrap
from pathlib import Path

from mu.reflexes.makefile import fix_makefile_executable_prerequisites


def _mk(tmp_path, content):
    p = tmp_path / 'Makefile'
    p.write_text(textwrap.dedent(content))
    return p


def test_removes_pip_prerequisite(tmp_path):
    p = _mk(tmp_path, """\
        venv: pip
        \tpip install -r requirements.txt

        test: venv
        \t.venv/bin/pytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is True
    content = p.read_text()
    assert 'venv: pip' not in content
    assert 'venv:' in content
    assert '\tpip install -r requirements.txt' in content


def test_removes_pytestmain_prerequisite(tmp_path):
    p = _mk(tmp_path, """\
        test: pytestmain
        \tpytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is True
    content = p.read_text()
    assert 'pytestmain' not in content
    assert 'test:' in content
    assert '\tpytest' in content


def test_removes_python3_prerequisite(tmp_path):
    p = _mk(tmp_path, """\
        deps: python3
        \tpython3 -m venv .venv

        test: deps
        \t.venv/bin/pytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is True
    content = p.read_text()
    assert 'deps: python3' not in content
    assert 'deps:' in content


def test_no_fire_when_declared_as_target(tmp_path):
    """If 'pip' is actually defined as a target, don't remove it."""
    p = _mk(tmp_path, """\
        pip:
        \twhich pip

        venv: pip
        \tpip install flask
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is False


def test_preserves_file_prerequisites(tmp_path):
    """requirements.txt has a dot — should not be flagged."""
    p = _mk(tmp_path, """\
        venv: requirements.txt
        \tpip install -r requirements.txt

        test: venv
        \tpytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is False


def test_preserves_venv_target_prerequisite(tmp_path):
    """When 'venv' is a declared target, `test: venv` should be kept."""
    p = _mk(tmp_path, """\
        venv:
        \tpython3 -m venv .venv && .venv/bin/pip install flask pytest

        test: venv
        \t.venv/bin/pytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is False


def test_removes_multiple_bad_prereqs(tmp_path):
    p = _mk(tmp_path, """\
        setup: pip python3
        \tpip install -r requirements.txt

        test:
        \tpytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is True
    content = p.read_text()
    assert 'pip' not in content.split('\n')[0]
    assert 'python3' not in content.split('\n')[0]
    assert 'setup:' in content


def test_idempotent(tmp_path):
    p = _mk(tmp_path, """\
        venv: pip
        \tpip install flask

        test: venv
        \tpytest
        """)
    fix_makefile_executable_prerequisites(str(p))
    first = p.read_text()
    fix_makefile_executable_prerequisites(str(p))
    second = p.read_text()
    assert first == second


def test_no_fire_on_phony(tmp_path):
    """.PHONY: pip should not be touched."""
    p = _mk(tmp_path, """\
        .PHONY: pip test

        test:
        \tpytest
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is False


def test_variable_assignment_not_matched(tmp_path):
    """CC := gcc should not be treated as a rule."""
    p = _mk(tmp_path, """\
        CC := gcc
        CFLAGS = -Wall

        test:
        \t$(CC) $(CFLAGS) -o prog prog.c
        """)
    assert fix_makefile_executable_prerequisites(str(p)) is False
