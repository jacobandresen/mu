"""ground_plan must complete an ASP.NET minimal-API plan that omits its entry point.

Once the MSB1003 test-command fix lets `dotnet test` reach compilation, the dominant
p10 backend_build first-error is CS0246 — `WebApplicationFactory<Program>` referenced
by the integration test, but the architect planned Models/DbContext/Controllers and
*never* an entry point, so no `Program` type exists (archive scan 2026-06-23, 6/15).

The fix adds the entry-point **task** (the writer authors the code — no pregenerated
code, §0.2), gated behind MU_ASPNET_ENTRYPOINT (I1: off ⇒ byte-identical). It must:
fire for an aspnet goal lacking an entry file; no-op when one is planned, when the goal
is a plain C# console problem (protects the p4 control), and when the flag is off.
"""
import os
from pathlib import Path

import pytest

from mu.plan import ground_plan, parse, parse_content

ASPNET_PLAN = """\
## Summary
ASP.NET Core minimal API blog with EF Core + an xUnit WebApplicationFactory test.

## Files
- [ ] backend/Models/Post.cs — Post entity
- [ ] backend/Infrastructure/AppDb.cs — EF Core DbContext
- [ ] tests/ApiTests.cs — xUnit WebApplicationFactory test for GET /api/posts

## Test Command
```sh
dotnet test
```
"""

CONSOLE_PLAN = """\
## Summary
A C# console app that prints the Fibonacci sequence.

## Files
- [ ] Fibonacci.cs — compute and print fib(n)

## Test Command
```sh
dotnet test
```
"""


def _ground(tmp_path, plan_text, env):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    old = os.environ.get('MU_ASPNET_ENTRYPOINT')
    try:
        if env is None:
            os.environ.pop('MU_ASPNET_ENTRYPOINT', None)
        else:
            os.environ['MU_ASPNET_ENTRYPOINT'] = env
        Path('PLAN.md').write_text(plan_text)
        ground_plan('PLAN.md', parse_content(plan_text))
        text = Path('PLAN.md').read_text()
        files = [t.file_path for t in parse('PLAN.md').tasks]
        return text, files
    finally:
        if old is None:
            os.environ.pop('MU_ASPNET_ENTRYPOINT', None)
        else:
            os.environ['MU_ASPNET_ENTRYPOINT'] = old
        os.chdir(cwd)


def test_injects_entrypoint_for_aspnet_goal(tmp_path):
    text, files = _ground(tmp_path, ASPNET_PLAN, '1')
    assert 'Program.cs' in files
    assert 'public partial class Program' in text          # the testability hint
    # planned as an unchecked task (the writer authors it, not grounding)
    assert '- [ ] Program.cs' in text


def test_noop_when_flag_off(tmp_path):
    text, files = _ground(tmp_path, ASPNET_PLAN, None)
    assert 'Program.cs' not in files


def test_noop_when_entrypoint_already_planned(tmp_path):
    plan = ASPNET_PLAN.replace(
        '- [ ] tests/ApiTests.cs',
        '- [ ] Program.cs — minimal API host\n- [ ] tests/ApiTests.cs')
    text, files = _ground(tmp_path, plan, '1')
    assert files.count('Program.cs') == 1                  # not duplicated


def test_noop_for_plain_console_csharp(tmp_path):
    # No aspnet/EF/WebApplicationFactory keywords ⇒ needs_ef False ⇒ no entry point
    # (this is the p4-fibonacci control path — must stay byte-identical).
    _, files = _ground(tmp_path, CONSOLE_PLAN, '1')
    assert 'Program.cs' not in files


def test_idempotent(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    os.environ['MU_ASPNET_ENTRYPOINT'] = '1'
    try:
        Path('PLAN.md').write_text(ASPNET_PLAN)
        ground_plan('PLAN.md', parse('PLAN.md'))
        ground_plan('PLAN.md', parse('PLAN.md'))           # second pass
        files = [t.file_path for t in parse('PLAN.md').tasks]
        assert files.count('Program.cs') == 1
    finally:
        os.environ.pop('MU_ASPNET_ENTRYPOINT', None)
        os.chdir(cwd)


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
