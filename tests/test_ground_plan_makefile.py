"""ground_plan must not hand a Python project a C compile Makefile.

Regression for the dominant p7-flask failure: the planner names a `make test`
command but no Makefile, Level 2b synthesized a `cc -o main main.c` template
(with the `test:` recipe a stray `pytest`), the makefile reflexes then hoisted
the bogus rule out, and `make test` reported "no rule to make target 'test'".
The C `cc -o` fallback must fire only for projects that actually have C sources;
Python projects must get the venv Makefile (Level 4a) with a real `test:` target.
"""
import os
from pathlib import Path

import pytest

from mu.plan import ground_plan, parse_content


def _ground(tmp_path, plan_text):
    """Run ground_plan with cwd at a fresh dir; return the Makefile text ('' if none)."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        plan_path = Path('PLAN.md')
        plan_path.write_text(plan_text)
        p = parse_content(plan_text)
        changes = ground_plan(str(plan_path), p)
        mk = Path('Makefile')
        return (mk.read_text() if mk.exists() else ''), changes
    finally:
        os.chdir(cwd)


PY_FLASK_PLAN = """\
## Summary
Flask REST API with SQLite.

## Files
- [ ] main.py — Flask app
- [ ] test_main.py — pytest tests

## Test Command
make test
"""


def test_python_plan_gets_venv_makefile_with_real_test_target(tmp_path):
    makefile, changes = _ground(tmp_path, PY_FLASK_PLAN)
    assert makefile, "a Makefile should have been synthesized"
    # No C compile rule leaked into a Python project.
    assert 'cc -o' not in makefile
    assert 'main.c' not in makefile
    # `make test` must have something to run: a real test target with a recipe.
    assert 'test:' in makefile
    lines = makefile.splitlines()
    test_idx = next(i for i, ln in enumerate(lines) if ln.startswith('test:'))
    recipe = lines[test_idx + 1] if test_idx + 1 < len(lines) else ''
    assert recipe.startswith('\t'), "the test target needs a recipe line"
    assert 'pytest' in makefile


def test_python_plan_makefile_actually_runs_test(tmp_path):
    """The grounded Makefile must satisfy `make -n test` (a rule exists)."""
    import shutil
    import subprocess

    if not shutil.which('make'):
        pytest.skip('make not installed')
    makefile, _ = _ground(tmp_path, PY_FLASK_PLAN)
    (tmp_path / 'Makefile').write_text(makefile)
    r = subprocess.run(['make', '-n', 'test'], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, f"`make -n test` failed: {r.stderr}"
    assert 'No rule to make target' not in r.stderr


C_PLAN = """\
## Summary
Hello world in C.

## Files
- [ ] hello.c — the program

## Test Command
make && ./hello
"""


def test_c_plan_still_gets_compile_makefile(tmp_path):
    """The C fallback must remain intact for actual C projects."""
    makefile, changes = _ground(tmp_path, C_PLAN)
    assert makefile, "a C project with `make` and no Makefile still needs one"
    assert 'cc -o' in makefile
    assert 'hello.c' in makefile
