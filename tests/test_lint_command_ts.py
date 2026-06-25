"""_lint_command's TypeScript branch must use project mode when a tsconfig exists on
disk (not only as a plan task) — else `tsc --noEmit <file>` trips TS5112 'tsconfig.json
is present but will not be loaded if files are specified on commandline' (seen on the
Vue/Vitest goals, where the model writes tsconfig.json without it being a planned task).
"""
import shutil

from mu.agent import _lint_command
from mu.plan import parse


def _plan(tmp_path, body):
    pf = tmp_path / 'PLAN.md'
    pf.write_text(body)
    return parse(str(pf))


def test_ts_project_mode_when_tsconfig_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda b: '/usr/bin/tsc' if b == 'tsc' else None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'node_modules').mkdir()          # past the missing-deps early return
    (tmp_path / 'tsconfig.json').write_text('{}')  # on disk, NOT a plan task
    p = _plan(tmp_path, "## Files\n- [ ] app.ts the app\n")
    assert _lint_command('app.ts', p) == 'tsc --noEmit'   # no file on the command line


def test_ts_file_mode_when_no_tsconfig(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda b: '/usr/bin/tsc' if b == 'tsc' else None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'node_modules').mkdir()
    p = _plan(tmp_path, "## Files\n- [ ] app.ts the app\n")
    cmd = _lint_command('app.ts', p)
    assert cmd.startswith('tsc --noEmit') and cmd.endswith('app.ts')  # file mode, no tsconfig
