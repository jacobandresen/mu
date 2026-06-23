"""normalize_test_command must redirect a `dotnet test <dir>` command that
resolves to no project file — the dominant p10 MSB1003 bottleneck.

The model authors `## Test Command: dotnet test tests/` (a conventional separate
xUnit project) but the writer produces a single root project and never creates
`tests/*.csproj`. Grounding adds the root `.csproj` but, before this fix, the
redirect only fired when `tests/` already existed (`arg_path.is_dir()`) — and at
grounding time the writer has not created it yet. So the stale `dotnet test tests/`
survived into the gate and failed with:

    MSBUILD : error MSB1003: Specify a project or solution file.

The redirect now fires whenever `<dir>` holds no `.csproj` (absent, a file, or a
csproj-less dir), while leaving a real test project (`tests/Foo.csproj`) alone.
"""
import os
from pathlib import Path

import pytest

from mu.plan import normalize_test_command, parse_content

_PLAN = """\
## Summary
blog

## Files
- [ ] Models/Post.cs — model

## Test Command
```sh
dotnet test tests/
```
"""


def _normalized(tmp_path, build):
    """Write the plan, run *build*(dir) to lay out the tree, normalize, return cmd."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        Path('PLAN.md').write_text(_PLAN)
        build(Path('.'))
        changed = normalize_test_command('PLAN.md')
        return parse_content(Path('PLAN.md').read_text()).test_command, changed
    finally:
        os.chdir(cwd)


def test_absent_dir_no_csproj_yet_redirects_to_bare(tmp_path):
    # Grounding-time p10 reality: tests/ not created, root .csproj not added yet.
    # Bare `dotnet test` auto-discovers the root project ground_plan adds next.
    cmd, changed = _normalized(tmp_path, lambda p: None)
    assert cmd == 'dotnet test'
    assert changed


def test_absent_dir_with_root_csproj_redirects_to_root(tmp_path):
    cmd, changed = _normalized(
        tmp_path, lambda p: (p / 'App.csproj').write_text('<Project/>'))
    assert cmd == 'dotnet test App.csproj'
    assert changed


def test_csproj_less_dir_redirects_to_root(tmp_path):
    def build(p):
        (p / 'tests').mkdir()
        (p / 'App.csproj').write_text('<Project/>')
    cmd, changed = _normalized(tmp_path, build)
    assert cmd == 'dotnet test App.csproj'
    assert changed


def test_real_test_project_is_left_untouched(tmp_path):
    # A genuine multi-project layout — do NOT redirect away from the test project.
    def build(p):
        (p / 'tests').mkdir()
        (p / 'tests' / 'T.csproj').write_text('<Project/>')
    cmd, changed = _normalized(tmp_path, build)
    assert cmd == 'dotnet test tests/'
    assert not changed


def test_idempotent(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        Path('PLAN.md').write_text(_PLAN)
        assert normalize_test_command('PLAN.md')        # first pass rewrites
        assert not normalize_test_command('PLAN.md')    # second pass is a no-op
    finally:
        os.chdir(cwd)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
