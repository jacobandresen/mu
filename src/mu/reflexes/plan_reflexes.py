"""Plan reflexes: deterministic clarifications applied to PLAN.md task
descriptions. They enrich the spec the writer sees (interface/test-harness
contracts) WITHOUT adding, removing, or renaming tasks — the honest, decompose-
free form of ``mu improve``. Split out of the monolithic reflexes module so
each concern lives in its own module. No logic changes from the original.
"""

import re
from pathlib import Path

from mu.plan import is_test_file


__all__ = [
    'apply_plan_spec_reflexes',
]


_PLAN_PENDING_RE = re.compile(r'^(- \[ \] )(\S+)(.*)$')

def _plan_spec_directives(goal: str, file_path: str) -> list[tuple[str, str]]:
    """(keyword, clause) contract directives for one task, by file type + goal.

    The keyword is a distinctive token used to skip a directive already present,
    so the reflex is idempotent. Clauses mirror the test-isolation / no-server /
    storage rules in the skills, phrased as a short spec the writer can follow.
    """
    g = goal.lower()
    ext = Path(file_path).suffix.lower()
    is_test = is_test_file(file_path)
    has_db = any(k in g for k in ('sqlite', 'database', ' db ', 'storage', 'todo'))
    has_http = any(k in g for k in ('http', 'api', 'server', 'rest', 'endpoint',
                                    'flask', 'gin', 'express', 'asp.net', 'ping', '/todos'))
    d: list[tuple[str, str]] = []
    if is_test:
        if ext == '.py':
            d.append(('test_client',
                      'tests must drive the app via Flask app.test_client() in-process — never start a live server'))
            if has_db:
                d.append(('in-memory', 'use an in-memory SQLite that resets each test'))
        elif ext == '.go':
            d.append(('httptest',
                      'test handlers via httptest.NewRecorder and a setup function — do not start a live server'))
        elif ext in ('.js', '.ts'):
            d.append(('supertest',
                      'test the exported app with supertest/jest — the app module must not call listen()'))
        elif ext == '.cs':
            d.append(('WebApplicationFactory',
                      'use WebApplicationFactory<Program> in-process with Data Source=:memory:'))
    else:
        if ext == '.py' and has_db:
            d.append(('sqlite3', 'use the sqlite3 stdlib with one persistent connection — no ORM'))
        if ext == '.go' and has_http:
            d.append(('setupRouter', 'expose a setupRouter() that returns the engine without calling Run()'))
        if ext in ('.js', '.ts') and has_http:
            d.append(('listen', 'export the app without calling listen(); start the server in a separate entry file'))
        if ext == '.cs' and has_http:
            d.append(('partial class Program', 'end Program.cs with `public partial class Program {}` so tests can host it'))
    return d

def apply_plan_spec_reflexes(goal: str, plan_file: str) -> list[str]:
    """Enrich pending task descriptions in PLAN.md with deterministic interface /
    test-harness contracts. Never adds, removes, or renames tasks — clarification
    only. Returns a list of human-readable notes (one per task changed)."""
    try:
        lines = Path(plan_file).read_text().splitlines(keepends=True)
    except OSError:
        return []
    notes: list[str] = []
    changed = False
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        m = _PLAN_PENDING_RE.match(stripped)
        if not m:
            continue
        prefix, path, rest = m.groups()
        directives = _plan_spec_directives(goal, path.strip('`*'))
        if not directives:
            continue
        rest_l = rest.lower()
        to_add = [clause for kw, clause in directives if kw.lower() not in rest_l]
        if not to_add:
            continue
        # Ensure the line has an em-dash description separator to append onto.
        base = stripped if '—' in stripped else f"{stripped} —"
        newline = base.rstrip() + ' [spec: ' + '; '.join(to_add) + ']'
        lines[i] = newline + ('\n' if line.endswith('\n') else '')
        notes.append(f"{path.strip('`*')}: +{len(to_add)} contract(s)")
        changed = True
    if not changed:
        return []
    Path(plan_file).write_text(''.join(lines))
    return notes
