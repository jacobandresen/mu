"""Simple-reflex condition-action rules (effectors) applied after model writes.

The agent's reflex layer — condition → action rules with no memory that repair
general-class errors in model output before the lint/test gates run. These are
*effectors*, not sensors: they change the world (rewrite files) rather than
observe it. The real sensors (percepts) live in ``tools._read`` and gate stdout.

Each function corrects a *general class* of model error, independent of any
specific dojo problem. The honesty test: would you write this fix for any
program in this language or build system? If the answer is "no, only because
problem X needs it," the reflex is overfit — don't add it.
"""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from mu.plan import is_test_file

# Per-language reflex modules. Each owns the fixers for one language/build
# system; re-exported here so callers keep importing from ``mu.reflexes``.
from mu.reflexes.core import *  # noqa: E402,F401,F403
from mu.reflexes.rust import *  # noqa: E402,F401,F403
from mu.reflexes.csharp import *  # noqa: E402,F401,F403
from mu.reflexes.go import *  # noqa: E402,F401,F403
from mu.reflexes.javascript import *  # noqa: E402,F401,F403





# A Makefile target at column 0: a plain name (all, .PHONY) OR a make variable
# ($(EXEC), ${PROG}) used as a target name, followed by a colon. Small models
# routinely write `$(EXEC): main.c`; without the variable form the reflexes
# that key off this regex mis-classify such lines as orphan recipes.
_TARGET_RE = re.compile(r'(?m)^(?:\$[({][A-Za-z_]\w*[)}]|[a-zA-Z_.][a-zA-Z0-9._-]*)\s*:')
_KNOWN_TARGETS = {'all', 'clean', 'install', 'test', 'build', 'run', 'format',
                  'lint', 'check', 'release', 'debug', 'help'}
_INLINE_COMPILER_RE = re.compile(
    r'^(?:cc|clang|gcc|g\+\+|clang\+\+|go|cargo|dotnet|python3?|rustc|make)\b'
)


# ── Python reflexes ───────────────────────────────────────────────────────────

def fix_multiline_single_quote(file_path: str, lint_error: str) -> bool:
    """Replace multi-line single-quoted SQL strings with triple-quoted strings."""
    if not file_path.endswith('.py') or 'invalid-syntax' not in lint_error:
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    lines = data.splitlines()
    changed, i, result = False, 0, []
    while i < len(lines):
        line = lines[i]
        idx = line.find(".execute('")
        if idx >= 0:
            open_pos = idx + len(".execute(")
            if "'" not in line[open_pos + 1:]:
                line = line[:open_pos] + '"""' + line[open_pos + 1:]
                result.append(line)
                i += 1
                while i < len(lines):
                    inner, stripped = lines[i], lines[i].strip()
                    if stripped.endswith("'')"):
                        close = inner.rfind("'')")
                        inner = inner[:close] + '""")' + inner[close + 3:]
                        changed = True
                        result.append(inner)
                        i += 1
                        break
                    elif stripped.endswith("')"):
                        close = inner.rfind("')")
                        inner = inner[:close] + '""")' + inner[close + 2:]
                        changed = True
                        result.append(inner)
                        i += 1
                        break
                    result.append(inner)
                    i += 1
                continue
        result.append(line)
        i += 1
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result))
    return True


def fix_missing_close_paren(file_path: str, lint_error: str) -> bool:
    """Add missing ) after triple-quoted execute() call."""
    if not file_path.endswith('.py') or 'invalid-syntax' not in lint_error:
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    lines = data.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if line.strip() != '"""':
            continue
        for j in range(i - 1, -1, -1):
            prev = lines[j]
            if '.execute("""' in prev and '""")' not in prev:
                lines[i] = line + ')'
                changed = True
                break
            if '""")' in prev:
                break
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(lines))
    return True


def fix_test_import_module(file_path: str) -> bool:
    """Fix test files that import a module name that doesn't exist on disk."""
    if not file_path.endswith('.py'):
        return False
    stem = Path(file_path).stem.lower()
    if not (stem.startswith('test_') or stem.endswith('_test')):
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    file_dir = Path(file_path).parent
    candidates = [e.name[:-3] for e in file_dir.iterdir()
                  if e.name.endswith('.py') and not e.name.startswith('test_')
                  and not e.name.endswith('_test.py')]
    changed, lines = False, data.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from ') and len(stripped.split()) >= 2:
            module_name = stripped.split()[1]
        elif stripped.startswith('import ') and len(stripped.split()) >= 2:
            module_name = stripped.split()[1].split('.')[0]
        else:
            continue
        if (file_dir / (module_name + '.py')).exists():
            continue
        ml = module_name.lower()
        best = next((c for c in candidates
                     if ml.startswith(c.lower()) or c.lower().startswith(ml)
                     or c.lower() in ml or ml in c.lower()), '')
        if best and best != module_name:
            lines[i] = line.replace(module_name, best)
            changed = True
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(lines))
    return True


def py_autofix(file_path: str) -> bool:
    """Strip unused imports/variables from a Python file (pure-Python autoflake).

    Mirrors the autofixable subset of ``ruff --select=E9,F`` (F401/F841).
    Returns True if the file was processed.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        import autoflake
    except ImportError:
        return False
    try:
        src = Path(file_path).read_text()
        fixed = autoflake.fix_code(src, remove_all_unused_imports=True,
                                   remove_unused_variables=True)
        if fixed != src:
            Path(file_path).write_text(fixed)
    except (OSError, SyntaxError, ValueError):
        return False
    return True


_PY_STDLIB_IMPORTS = {
    'sqlite3': 'import sqlite3',
    'json': 'import json',
    'os': 'import os',
    'sys': 'import sys',
    're': 'import re',
    'math': 'import math',
    'random': 'import random',
    'datetime': 'from datetime import datetime',
    'threading': 'import threading',
    'subprocess': 'import subprocess',
    'pathlib': 'from pathlib import Path',
    'collections': 'import collections',
    'itertools': 'import itertools',
    'functools': 'import functools',
    'typing': 'from typing import List, Dict, Optional',
    'dataclasses': 'from dataclasses import dataclass',
    'abc': 'from abc import ABC, abstractmethod',
    'uuid': 'import uuid',
    'hashlib': 'import hashlib',
    'base64': 'import base64',
    'copy': 'import copy',
    'time': 'import time',
    'logging': 'import logging',
}


def _sibling_py_sources(file_path: str) -> dict[str, str]:
    """Return {stem: source} for non-test .py siblings of file_path."""
    fp = Path(file_path)
    return {p.stem: p.read_text()
            for p in fp.parent.glob('*.py')
            if p.stem != fp.stem and not p.stem.startswith('test_')}


def _insert_py_imports(file_path: str, stmts: list[str]) -> None:
    """Insert import statements after the last existing import line."""
    lines = Path(file_path).read_text().splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('import ', 'from ')):
            insert_at = i + 1
        elif line and not line.startswith('#') and insert_at > 0:
            break
    for stmt in reversed(stmts):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')


def fix_python_missing_project_imports(file_path: str) -> bool:
    """Add missing imports for project-local names used but not imported in test files.

    Test files often use `app`, `db`, `client` and similar objects defined in
    the implementation module (app.py, models.py) without importing them. This
    reflex detects usage of names that match symbols exported by sibling .py files
    and adds the missing import.
    General: uses file existence and name matching, not problem-specific patterns.
    """
    if not file_path.lower().endswith('.py'):
        return False
    fp = Path(file_path)
    if not fp.stem.startswith('test_'):
        return False
    try:
        text = fp.read_text()
    except OSError:
        return False
    sibling_modules = list(_sibling_py_sources(file_path))
    if not sibling_modules:
        return False
    # `from mod import mod` for each sibling module name used but not yet imported.
    to_add = [
        f'from {mod} import {mod}'
        for mod in sibling_modules
        if re.search(rf'\b{re.escape(mod)}\b', text)
        and not re.search(rf'(?:import {re.escape(mod)}\b|from {re.escape(mod)}\b)', text)
    ]
    if not to_add:
        return False
    _insert_py_imports(file_path, to_add)
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing project import(s) to {file_path}: {to_add}")
    return True


def fix_python_undefined_imports(file_path: str, lint_error: str) -> bool:
    """Add imports for symbols reported as undefined by flake8 (F821/F811).

    Parses ``undefined name 'X'`` entries from the lint output, then searches
    sibling .py files for where X is defined (top-level assignment, class, or
    function), and adds ``from <module> import X`` statements. Generic: driven
    entirely by the lint error and file contents, not any specific problem.
    """
    if not file_path.lower().endswith('.py'):
        return False
    if 'undefined name' not in lint_error:
        return False
    undefined = set(re.findall(r"undefined name '(\w+)'", lint_error))
    if not undefined:
        return False
    fp = Path(file_path)
    try:
        text = fp.read_text()
    except OSError:
        return False
    sibling_sources = _sibling_py_sources(file_path)
    to_add = []
    for name in sorted(undefined):
        if re.search(rf'(?:import {re.escape(name)}\b|from \S+ import .*\b{re.escape(name)}\b)', text):
            continue
        for mod, src in sibling_sources.items():
            if re.search(rf'(?m)^(?:class|def)\s+{re.escape(name)}\b', src) or \
               re.search(rf'(?m)^\s*{re.escape(name)}\s*=', src):
                to_add.append((mod, name))
                break
    if not to_add:
        return False
    by_mod: dict[str, list[str]] = {}
    for mod, sym in to_add:
        by_mod.setdefault(mod, []).append(sym)
    stmts = [f"from {mod} import {', '.join(sorted(syms))}" for mod, syms in sorted(by_mod.items())]
    _insert_py_imports(file_path, stmts)
    print(f"==> [mu-agent] Reflex: added undefined-name imports to {file_path}: {stmts}")
    return True


def fix_sqlite_test_isolation(file_path: str) -> bool:
    """Replace file-based SQLite paths with ':memory:' in any Python file in a tested project.

    Tests that open a named SQLite file accumulate state across test functions
    and across repair iterations, causing inflated row counts and assertion
    failures. Using ':memory:' gives each connection a fresh database. Fires on
    any .py file (implementation or test) when the project directory contains at
    least one test file — the presence of tests indicates this is a test
    scenario where in-memory SQLite is always correct.
    """
    if not file_path.lower().endswith('.py'):
        return False
    parent = Path(file_path).parent
    has_tests = any(parent.glob('test_*.py'))
    if not has_tests:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Replace SQLAlchemy-style connection strings first (sqlite:///filename.db)
    # SQLAlchemy in-memory URL is 'sqlite:///:memory:', not ':memory:'.
    new_text = re.sub(
        r"sqlite:///[^'\"]*(?:\.db|\.sqlite3?)",
        'sqlite:///:memory:',
        text,
    )
    # Replace quoted .db / .sqlite file paths with ':memory:' for direct sqlite3
    new_text = re.sub(r'''(['"])(?:[^'"]*(?:\.db|\.sqlite3?))\1''', "':memory:'", new_text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced SQLite file path(s) with :memory: in {file_path}")
    return True


def fix_sqlite_memory_multi_connect(file_path: str) -> bool:
    """Consolidate multiple sqlite3.connect(':memory:') calls to one persistent connection.

    After fix_sqlite_test_isolation converts paths to ':memory:', classes that open
    a new connection per method each get a fresh empty database — the table created
    in __init__/_create_table doesn't exist in the connection opened by add()/list().

    Detects: self.X stored as ':memory:' AND sqlite3.connect(self.X) in 2+ methods.
    Transforms: adds self._conn = sqlite3.connect(':memory:') in __init__,
                replaces per-method sqlite3.connect(self.X) with conn = self._conn.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    if text.count('sqlite3.connect(') < 2:
        return False

    # Find: self.X = ':memory:' (the stored path attribute)
    attr_m = re.search(r"^([ \t]+)(self\.(\w+))\s*=\s*['\"]?:memory:['\"]?$",
                       text, re.MULTILINE)
    if not attr_m:
        return False

    self_attr = attr_m.group(2)    # e.g. self.db_path

    # Confirm the attribute is used in 2+ sqlite3.connect() calls
    connect_re = re.compile(
        r'(\w+)\s*=\s*sqlite3\.connect\(\s*' + re.escape(self_attr) + r'\s*\)'
    )
    if len(connect_re.findall(text)) < 2:
        return False

    # 1. Add self._conn = sqlite3.connect(':memory:') + row_factory after the attr line
    new_text = re.sub(
        r'^([ \t]+)' + re.escape(self_attr) + r"\s*=\s*['\"]?:memory:['\"]?$",
        lambda mo: (
            f"{mo.group(1)}{self_attr} = ':memory:'\n"
            f"{mo.group(1)}self._conn = sqlite3.connect(':memory:')\n"
            f"{mo.group(1)}self._conn.row_factory = sqlite3.Row"
        ),
        text, count=1, flags=re.MULTILINE,
    )

    # 2. Replace per-method connects with self._conn
    new_text = connect_re.sub('conn = self._conn', new_text)

    # 3. Remove lines that immediately follow conn = self._conn that are now
    #    redundant or harmful: row_factory assignments and conn.close() calls.
    #    conn.close() on self._conn would close the persistent connection.
    new_text = re.sub(
        r'(conn = self\._conn\n)([ \t]*)conn\.row_factory\s*=\s*sqlite3\.Row\n',
        r'\1',
        new_text,
    )
    # Remove bare conn.close() calls throughout — the persistent connection
    # must not be closed between method calls.
    new_text = re.sub(r'^[ \t]*conn\.close\(\)\n', '', new_text, flags=re.MULTILINE)

    if new_text == text:
        return False

    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: consolidated :memory: SQLite connections in {file_path}")
    return True


def fix_sqlite_path_unlink(file_path: str) -> bool:
    """Wrap bare attribute .unlink() calls with Path() in Python test files.

    Models write teardown code like `manager.db_path.unlink(missing_ok=True)`
    but db_path is a plain string, not a Path object, so this raises
    AttributeError. Replace with `Path(manager.db_path).unlink(...)`.
    Only fires on test files to avoid touching production code.
    """
    if not file_path.lower().endswith('.py'):
        return False
    base = Path(file_path).name
    if not (base.startswith('test_') or '_test.' in base):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Match: anything.db_path.unlink( or anything.db.unlink(
    new_text = re.sub(
        r'\b(\w+(?:\.\w+)*\.(?:db_path|db_file|database_path|database|sqlite_path))'
        r'(\.unlink\()',
        r'Path(\1)\2',
        text,
    )
    if new_text == text:
        return False
    # Ensure pathlib is imported
    if 'from pathlib import Path' not in new_text and 'import pathlib' not in new_text:
        new_text = 'from pathlib import Path\n' + new_text
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: wrapped db_path.unlink() with Path() in {file_path}")
    return True


def fix_python_missing_stdlib_imports(file_path: str) -> bool:
    """Add missing stdlib imports for identifiers used but not imported.

    Scans for `name.` or `name(` usage patterns that require a stdlib import
    and adds the import if it's absent. General: applies to any Python file,
    not specific to any problem domain.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    to_add = []
    for name, stmt in _PY_STDLIB_IMPORTS.items():
        already = re.search(rf'^(?:import {name}|from {name}\b)', text, re.MULTILINE)
        if already:
            continue
        if re.search(rf'\b{name}[\.(]', text):
            to_add.append(stmt)
    if not to_add:
        return False
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('import ', 'from ')):
            insert_at = i + 1
        elif line and not line.startswith('#') and insert_at > 0:
            break
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing stdlib import(s) to {file_path}: {to_add}")
    return True




_STDLIB_MODULES = {
    'os', 'sys', 're', 'json', 'math', 'time', 'datetime', 'pathlib',
    'collections', 'itertools', 'functools', 'typing', 'io', 'abc',
    'random', 'string', 'struct', 'copy', 'enum', 'dataclasses',
    'subprocess', 'threading', 'multiprocessing', 'socket', 'http',
    'urllib', 'hashlib', 'base64', 'uuid', 'logging', 'unittest',
    'contextlib', 'weakref', 'gc', 'inspect', 'importlib', 'pkgutil',
    'ast', 'dis', 'pickle', 'shelve', 'csv', 'sqlite3', 'argparse',
    'shutil', 'tempfile', 'glob', 'fnmatch', 'stat', 'platform',
    'traceback', 'warnings', 'textwrap', 'pprint', 'decimal', 'fractions',
}

# Map import name → pip package name (when they differ)
_PIP_NAME: dict[str, str] = {
    'flask_sqlalchemy': 'flask-sqlalchemy',
    'flask_migrate': 'flask-migrate',
    'flask_login': 'flask-login',
    'flask_cors': 'flask-cors',
    'flask_restful': 'flask-restful',
    'dotenv': 'python-dotenv',
    'cv2': 'opencv-python',
    'PIL': 'Pillow',
    'sklearn': 'scikit-learn',
    'bs4': 'beautifulsoup4',
    'yaml': 'pyyaml',
    'attr': 'attrs',
    'dateutil': 'python-dateutil',
    'jwt': 'PyJWT',
    'pymongo': 'pymongo',
    'redis': 'redis',
    'celery': 'celery',
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'pydantic': 'pydantic',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'sqlalchemy': 'sqlalchemy',
}


def fix_requirements_stdlib_entries(req_path: str) -> bool:
    """Remove Python stdlib module names from requirements.txt.

    Models sometimes list stdlib modules (e.g. sqlite3, os, sys, json) in
    requirements.txt. These are not pip-installable and cause the entire
    ``pip install -r requirements.txt`` invocation to fail with "Could not
    find a version that satisfies <module>". When pytest is in the same
    invocation, pytest also fails to install, leaving .venv/bin/pytest absent.
    Generic: stdlib modules are never on PyPI, for any project.
    """
    if not str(req_path).endswith('requirements.txt'):
        return False
    try:
        text = Path(req_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    cleaned = []
    removed = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            cleaned.append(line)
            continue
        # Strip version specifiers to get bare package name
        pkg_name = re.split(r'[>=<!;\[]', stripped)[0].strip().lower().replace('-', '_')
        if pkg_name in _STDLIB_MODULES:
            removed.append(stripped)
        else:
            cleaned.append(line)
    if not removed:
        return False
    Path(req_path).write_text('\n'.join(cleaned) + '\n')
    print(f"==> [mu-agent] Reflex: removed stdlib entries from requirements.txt: {removed}")
    return True


def fix_missing_pip_packages(test_output: str, project_dir: str) -> bool:
    """Add missing pip packages to requirements.txt when tests fail with ModuleNotFoundError.

    Parses 'ModuleNotFoundError: No module named X' from test output, maps X to
    its pip package name, and adds it to requirements.txt (creating the file if
    needed). Generic: driven entirely by the error message, not any specific problem.
    """
    missing = re.findall(r"ModuleNotFoundError: No module named '([^']+)'", test_output)
    if not missing:
        return False
    # Normalise: take the top-level package name (e.g. 'flask_sqlalchemy.X' → 'flask_sqlalchemy')
    pkgs = {m.split('.')[0] for m in missing}
    # Skip stdlib
    pkgs -= _STDLIB_MODULES
    if not pkgs:
        return False
    req_path = Path(project_dir) / 'requirements.txt'
    try:
        existing = req_path.read_text() if req_path.exists() else ''
    except OSError:
        existing = ''
    existing_lower = existing.lower()
    to_add = [
        pip_name
        for pkg in sorted(pkgs)
        for pip_name in [_PIP_NAME.get(pkg, pkg.replace('_', '-'))]
        if pip_name.lower() not in existing_lower
    ]
    if not to_add:
        return False
    existing_lines = [l for l in existing.splitlines() if l.strip()]
    new_content = '\n'.join(existing_lines + to_add) + '\n'
    req_path.write_text(new_content)
    print(f"==> [mu-agent] Reflex: added missing packages to requirements.txt: {to_add}")
    return True









# Patterns that indicate a module is being used (mod.method or mod[...)






def fix_python_method_indent(file_path: str) -> bool:
    """Fix a `def` that lost its indentation after a class-level decorator.

    When a model writes `    @staticmethod\\ndef foo():` (decorator indented,
    def at column 0), Python raises IndentationError. This reflex re-indents
    the def line to match the decorator immediately above it.
    General: applies whenever an indented @decorator is followed by an unindented def.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    result = []
    changed = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if (i > 0 and stripped.startswith('def ') and not line[0].isspace()):
            prev = result[-1] if result else ''
            prev_stripped = prev.lstrip()
            if prev_stripped.startswith('@'):
                # Re-indent the def to match the decorator
                indent = prev[:len(prev) - len(prev_stripped)]
                result.append(indent + stripped)
                changed = True
                continue
        result.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: fixed method indentation after decorator in {file_path}")
    return True


def fix_python_decorator_colon(file_path: str) -> bool:
    """Remove spurious trailing colon from Python decorator lines.

    Models occasionally write `@decorator(...):` which is a SyntaxError —
    decorators must not end with a colon (the colon belongs on the def/class
    line below, not the decorator). This is a general error on any decorator,
    not specific to Flask.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    pattern = re.compile(r'^(@\w[\w.]*\(.*\))\s*:\s*$', re.MULTILINE)
    new_text, count = pattern.subn(r'\1', text)
    if not count:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed {count} spurious colon(s) from decorator(s) in {file_path}")
    return True






def fix_python_missing_def(file_path: str) -> bool:
    """Insert a missing `def funcname():` between an orphaned decorator and its body.

    Models occasionally write `@app.route(...)` immediately followed by the
    indented function body, skipping the `def` line entirely. Python raises
    `unexpected indent` on the first body line. This reflex synthesises a
    function name from the route path or decorator name and inserts the def.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    result = []
    changed = False
    used_names: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Collect a block of consecutive decorator lines
        if stripped.startswith('@'):
            decorator_block = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('@'):
                decorator_block.append(lines[j])
                j += 1
            # If the line after the decorators is indented (function body, not def/class)
            if (j < len(lines)
                    and lines[j].startswith((' ', '\t'))
                    and not lines[j].strip().startswith(('def ', 'async def ', 'class '))):
                # Synthesise a unique function name from route path + HTTP methods.
                last_dec = decorator_block[-1].strip()
                path_m = re.search(r"['\"/]([^'\"/?]+)", last_dec)
                method_m = re.search(r"methods\s*=\s*\[([^\]]+)\]", last_dec)
                base = ''
                if path_m:
                    base = re.sub(r'[^a-zA-Z0-9]', '_', path_m.group(1).strip('/'))
                if method_m:
                    methods = re.findall(r"['\"]([A-Z]+)['\"]", method_m.group(1))
                    if methods:
                        base = (base + '_' if base else '') + methods[0].lower()
                name = (base.strip('_') or 'handler')
                # Deduplicate: append suffix if name already used
                candidate, suffix = name, 2
                while candidate in used_names:
                    candidate = f'{name}_{suffix}'
                    suffix += 1
                name = candidate
                used_names.add(name)
                result.extend(decorator_block)
                result.append(f'def {name}():')
                changed = True
                i = j
                continue
            result.extend(decorator_block)
            i = j
            continue
        result.append(line)
        i += 1
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: inserted missing def(s) after orphaned decorator(s) in {file_path}")
    return True










# ── Flask / pytest reflexes ───────────────────────────────────────────────────

def fix_sqlite_missing_row_factory(file_path: str) -> bool:
    """Add conn.row_factory = sqlite3.Row after sqlite3.connect() calls.

    When a Flask app uses `dict(cursor.fetchone())` or `[dict(r) for r in ...]`
    on sqlite3 results but `conn.row_factory = sqlite3.Row` is not set, the
    result is a tuple and `dict(tuple)` raises TypeError. This reflex adds the
    row_factory assignment immediately after each sqlite3.connect() call.
    Generic: fires on any Python file that uses sqlite3.connect without row_factory.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fire if dict() is used on cursor results and row_factory is missing
    if 'row_factory' in text:
        return False  # already set
    if 'sqlite3.connect' not in text:
        return False
    if not re.search(r'\bdict\([^)]*\b(?:fetch|conn|cursor|row|todo|result)', text, re.IGNORECASE):
        # Also check for list comprehension with dict: [dict(r) for r in ...]
        if 'dict(r)' not in text and 'dict(t)' not in text and 'dict(row)' not in text:
            return False
    # Insert `conn.row_factory = sqlite3.Row` after each `sqlite3.connect(...)` assignment
    # Match patterns like: `    self.conn = sqlite3.connect(...)` or `conn = sqlite3.connect(...)`
    def _add_row_factory(m: re.Match) -> str:
        full = m.group(0)
        # Extract indentation and variable name
        indent_m = re.match(r'^([ \t]*)((?:self\.\w+|\w+))\s*=\s*sqlite3\.connect', full)
        if not indent_m:
            return full
        indent, varname = indent_m.group(1), indent_m.group(2)
        return full + f'{indent}{varname}.row_factory = sqlite3.Row\n'

    new_text = re.sub(
        r'[ \t]*(?:self\.\w+|\w+)\s*=\s*sqlite3\.connect\([^\n]*\)\n',
        _add_row_factory,
        text
    )
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added row_factory = sqlite3.Row after sqlite3.connect in {file_path}")
    return True


def fix_flask_post_missing_201(file_path: str) -> bool:
    """Add HTTP 201 status code to Flask POST route returns missing it.

    REST convention: POST endpoints that create a resource should return 201.
    When a model writes `return jsonify(...)` in a POST handler without a
    status code, Flask defaults to 200, but tests that check `r.status_code == 201`
    fail. This reflex adds `, 201` to bare `return jsonify(...)` calls inside
    POST route handlers.
    Generic: applies to any Flask app with POST routes.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    if "@app.route" not in text or "methods=['POST']" not in text and 'methods=["POST"]' not in text:
        return False
    lines = text.splitlines()
    in_post_handler = False
    changed = False
    out = []
    for i, line in enumerate(lines):
        # Detect @app.route with POST
        if re.search(r"@\w+\.route\([^)]*methods=[^\)]*'POST'", line) or \
           re.search(r'@\w+\.route\([^)]*methods=[^\)]*"POST"', line):
            in_post_handler = True
        elif line.startswith('@') and 'route' in line:
            in_post_handler = False  # different decorator
        elif re.match(r'^def \w+', line):
            # New function def — if we were in a post handler, keep flag until a return is seen
            pass
        elif in_post_handler and re.match(r'\s+return jsonify\(', line):
            # Check if already has a status code (comma after the closing paren)
            stripped = line.rstrip()
            if not re.search(r'\bstatus\b', stripped) and not re.search(r'jsonify\(.*\),\s*\d+', stripped):
                # No status code — add 201
                stripped = re.sub(r'(return jsonify\(.*\))$', r'\1, 201', stripped)
                line = stripped + '\n' if line.endswith('\n') else stripped
                changed = True
                in_post_handler = False  # only fix the first return in the handler
        out.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: added 201 status to POST route jsonify return in {file_path}")
    return True


def fix_flask_test_route_decorators(file_path: str) -> bool:
    """Strip @app.route decorators from pytest test files.

    Models sometimes write Flask route handlers (`@app.route(...)`) inside test
    files that also import the Flask app. This causes two problems:
    1. "View function mapping is overwriting an existing endpoint function" — the
       test file re-registers routes already defined in app.py.
    2. The decorated functions are treated as Flask handlers, not pytest tests,
       so the `client` fixture parameter is misunderstood.

    Fires only on files whose name starts with `test_` or ends with `_test.py`.
    Generic: driven by the conflict pattern, not by any specific project.
    """
    if not file_path.lower().endswith('.py'):
        return False
    name = Path(file_path).name.lower()
    if not (name.startswith('test_') or name.endswith('_test.py')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    if 'app.route' not in text:
        return False
    # Remove @app.route(...) lines (possibly multi-line with methods=[...])
    new_text = re.sub(r'@app\.route\([^\)]*\)\n', '', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: stripped @app.route decorators from test file {file_path}")
    return True


def fix_flask_init_db_import(file_path: str) -> bool:
    """Remove `init_db` from Flask test imports when app.py doesn't define it.

    Models sometimes write `from app import app, init_db` in test files because
    the test client fixture calls `init_db()`. When `init_db` is not defined in
    app.py, pytest collection fails with ImportError. This reflex removes the
    `init_db` import AND any bare `init_db()` calls from the fixture body.
    Generic: fires whenever the imported symbol is absent in the source module.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only act on test files importing init_db from app
    if 'init_db' not in text:
        return False
    # Check if init_db is defined in app.py
    app_py = Path(file_path).parent / 'app.py'
    if not app_py.exists():
        return False
    app_text = app_py.read_text()
    if 'def init_db' in app_text:
        return False  # already defined, nothing to fix
    # Remove init_db from import line: `from app import app, init_db` → `from app import app`
    new_text = re.sub(
        r'(from\s+app\s+import\s+[^,\n]*)(?:,\s*init_db|init_db\s*,\s*)([^\n]*)',
        lambda m: m.group(1).rstrip(', ') + (' ' + m.group(2).strip() if m.group(2).strip() else ''),
        text
    )
    # Also handle: `from app import init_db` as the only import
    new_text = re.sub(r'from\s+app\s+import\s+init_db\s*\n', '', new_text)
    # Remove bare `init_db()` calls
    new_text = re.sub(r'^\s*(?:with\s+app\.app_context\(\)\s*:\s*)?init_db\(\)\s*\n', '', new_text, flags=re.MULTILINE)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed init_db import/call from {file_path} (not defined in app.py)")
    return True


def fix_missing_flask_client_fixture(file_path: str, test_output: str) -> bool:
    """Add a missing @pytest.fixture for Flask test client.

    When a pytest test file uses `client` as a parameter but no fixture named
    `client` is defined, pytest reports "fixture 'client' not found". For Flask
    projects, the correct pattern is to define a fixture that yields a test
    client from `app.test_client()`.

    Fires only when:
    - test output contains "fixture 'client' not found"
    - the file is a test file (starts with test_ or ends with _test.py)
    - the test file has test functions that accept `client` as a parameter
    - no `@pytest.fixture` with name `client` is already defined

    Generic: driven by the error message and test function pattern, not problem-specific.
    """
    if 'fixture \'client\' not found' not in test_output:
        return False
    if not file_path.lower().endswith('.py'):
        return False
    name = Path(file_path).name.lower()
    # Only fire on test files
    if not (name.startswith('test_') or name.endswith('_test.py')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fix if this file has test functions that use `client`
    if not re.search(r'def test_\w+\(client', text):
        return False
    # Only fire for Flask projects: find a sibling .py file that imports Flask
    parent = Path(file_path).parent
    flask_module = None
    for candidate in ['app.py', 'main.py', 'server.py', 'api.py']:
        cand = parent / candidate
        if cand.exists():
            try:
                if 'Flask' in cand.read_text():
                    flask_module = cand.stem  # 'app', 'main', etc.
                    break
            except OSError:
                pass
    if flask_module is None:
        return False
    # Don't add if fixture already exists
    if re.search(r'@pytest\.fixture\s*\ndef client', text):
        return False
    # Determine what app-level reset is needed (reset app._conn if app uses _conn pattern)
    flask_path = parent / (flask_module + '.py')
    has_conn_pattern = flask_path.exists() and '_conn' in flask_path.read_text()
    conn_reset = '    app._conn = None  # force fresh db per test\n' if has_conn_pattern else ''
    conn_teardown = '    app._conn = None  # cleanup\n' if has_conn_pattern else ''
    # Build the preamble (import app if not already there)
    needs_import = (f'from {flask_module} import app' not in text
                    and f'import {flask_module}' not in text)
    preamble = 'import pytest\n'
    if needs_import:
        preamble += f'from {flask_module} import app\n'
    preamble += '\n\n'
    fixture_block = (
        preamble +
        '@pytest.fixture\n'
        'def client():\n'
        '    app.config[\'TESTING\'] = True\n'
        '    app.config[\'DATABASE\'] = \':memory:\'\n' +
        conn_reset +
        '    with app.test_client() as c:\n'
        '        yield c\n' +
        conn_teardown +
        '\n\n'
    )
    # Insert the fixture after all imports but before first test function
    first_test = re.search(r'^def test_', text, re.MULTILINE)
    if first_test:
        insert_pos = first_test.start()
        new_text = text[:insert_pos] + fixture_block + text[insert_pos:]
    else:
        new_text = fixture_block + text
    # Deduplicate `import pytest` lines
    lines = new_text.split('\n')
    seen_pytest_import = False
    deduped = []
    for line in lines:
        if line.strip() == 'import pytest':
            if seen_pytest_import:
                continue
            seen_pytest_import = True
        deduped.append(line)
    new_text = '\n'.join(deduped)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added Flask client fixture to {file_path}")
    return True


# ── Makefile reflexes ─────────────────────────────────────────────────────────

def fix_makefile_space_indent(f: str) -> bool:
    """Fix recipe lines that are not tab-indented.

    Covers two cases:
    - Space-indented recipes (leading spaces → TAB).
    - Flush-left recipes (no leading whitespace after a target line → TAB added).
    Both produce "missing separator" from make.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if not _TARGET_RE.search(content):
        return False
    lines, changed, in_recipe, out = content.splitlines(), False, False, []
    for line in lines:
        trimmed = line.strip()
        if _TARGET_RE.match(line) and line and line[0] not in ('\t', ' '):
            in_recipe = True
            out.append(line)
        elif line and line[0] == '\t':
            in_recipe = True
            out.append(line)
        elif not trimmed:
            in_recipe = False
            out.append(line)
        elif in_recipe and line and line[0] == ' ':
            out.append('\t' + line.lstrip(' '))
            changed = True
        elif in_recipe and line and line[0] not in ('\t', '#') and not _TARGET_RE.match(line):
            # Flush-left command after a target — missing tab entirely.
            out.append('\t' + line)
            changed = True
        else:
            in_recipe = False
            out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True


def fix_orphan_top_level_commands(f: str) -> bool:
    """Wrap bare commands before the first target into an all: target."""
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if not _TARGET_RE.search(content):
        return False
    lines, seen_target, in_recipe, orphans, clean = content.splitlines(), False, False, [], []
    for line in lines:
        trimmed = line.strip()
        if _TARGET_RE.match(line) and line and line[0] not in ('\t', ' '):
            seen_target = True
            in_recipe = True
            clean.append(line)
        elif line and line[0] == '\t':
            if seen_target:
                in_recipe = True
                clean.append(line)
            else:
                # Tab-indented line before any target — causes "commands commence
                # before first target". Collect as an orphan to wrap into all:.
                orphans.append(line)
        elif not trimmed or trimmed.startswith('#'):
            in_recipe = False
            clean.append(line)
        elif not in_recipe and '=' not in trimmed and not trimmed.startswith('.'):
            orphans.append('\t' + trimmed)
        else:
            clean.append(line)
    if not orphans:
        return False
    all_re = re.compile(r'^all\s*:')
    for line in clean:
        if all_re.match(line):
            result, inserted = [], False
            for ln in clean:
                result.append(ln)
                if not inserted and all_re.match(ln):
                    result.extend(orphans)
                    inserted = True
            Path(f).write_text('\n'.join(result))
            return True
    Path(f).write_text('.DEFAULT_GOAL := all\n\nall:\n' + '\n'.join(orphans) +
                       '\n\n' + '\n'.join(clean))
    return True


def fix_no_targets(f: str) -> bool:
    """Wrap a plain-shell-script Makefile into an all: target."""
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if _TARGET_RE.search(content):
        return False
    recipes = ['\t' + ln.strip() for ln in content.rstrip('\n').splitlines()
               if ln.strip() and not ln.strip().startswith('#')]
    if not recipes:
        return False
    Path(f).write_text('.DEFAULT_GOAL := all\n\nall:\n' + '\n'.join(recipes) + '\n')
    return True


def fix_inline_recipe(f: str) -> bool:
    """Split inline recipes (target: command) onto separate lines."""
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    lines, changed, out = data.splitlines(), False, []
    for line in lines:
        trimmed = line.strip()
        if (line and line[0] != '\t' and not trimmed.startswith('#') and
                not trimmed.startswith('.') and '=' not in trimmed):
            colon = trimmed.find(':')
            if colon > 0 and colon < len(trimmed) - 1:
                target, after = trimmed[:colon].strip(), trimmed[colon + 1:].strip()
                is_known = target in _KNOWN_TARGETS
                is_compiler = _INLINE_COMPILER_RE.match(after)
                if (is_known or is_compiler) and ' ' in after and not after.startswith('='):
                    out.extend([target + ':', '\t' + after])
                    changed = True
                    continue
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True


def fix_makefile_backslash_artifact(f: str) -> bool:
    """Strip a stray backslash a model puts before inline whitespace on a target
    line, e.g. ``all: \\<TAB>$(EXEC)``.

    A real line-continuation backslash is the LAST character on its line; a
    backslash followed by more text on the same line is an artifact that mangles
    the prerequisite list. Restricted to target-definition lines (``name:``) so
    it never touches a recipe's legitimately-escaped space (``cp a\\ b``).
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    out, changed = [], False
    for line in content.splitlines():
        if re.match(r'^[A-Za-z0-9_.$(){}-]+\s*:', line) and re.search(r'\\[ \t]+\S', line):
            line = re.sub(r'\\[ \t]+(?=\S)', ' ', line)
            changed = True
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out) + '\n')
    return True


# Matches a tab-indented line that is really a target/directive, not a recipe:
# a plain name (hello, .PHONY) OR a make variable ($(EXEC), ${PROG}) followed by
# a colon. Small models emit `\t$(EXEC): main.c` and `\t.PHONY: all` indented
# under a prior target; both must be hoisted to column 0.
_NESTED_TARGET_RE = re.compile(r'^\t(\$[({][A-Za-z_]\w*[)}]|[A-Za-z0-9_.-]+):([ \t].*)?$')


def fix_nested_targets(f: str) -> bool:
    """Lift target definitions accidentally indented inside another recipe.

    Models sometimes indent the entire Makefile under a single ``all:`` block,
    writing ``\thello_world:`` and ``\trun:`` as recipe lines instead of
    top-level targets.  This reflex detects tab-prefixed ``word:`` lines inside
    a recipe and hoists them to column-0 targets.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    lines = content.splitlines()
    if not any(_NESTED_TARGET_RE.match(line) for line in lines):
        return False

    # Rebuild: scan line-by-line; when a misplaced target is found, extract it.
    out: list[str] = []
    extracted: list[list[str]] = []  # each element = [header, *recipe_lines]
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _NESTED_TARGET_RE.match(line)
        if m:
            name = m.group(1)
            deps = m.group(2).strip() if m.group(2) else ''
            header = (name + ': ' + deps) if deps else (name + ':')
            recipe: list[str] = [header]
            i += 1
            seen_cmds: set[str] = set()
            while i < len(lines):
                nxt = lines[i]
                if _NESTED_TARGET_RE.match(nxt):
                    break
                if not nxt.strip():
                    i += 1
                    break
                # Normalise to single-tab indented, deduplicate.
                cmd = '\t' + nxt.lstrip('\t')
                if cmd not in seen_cmds:
                    recipe.append(cmd)
                    seen_cmds.add(cmd)
                i += 1
            extracted.append(recipe)
        else:
            out.append(line)
            i += 1

    if not extracted:
        return False

    # If all: has no prerequisites, add the hoisted target names as deps
    # so `make` actually builds them.
    hoisted_names = [block[0].split(':')[0].strip() for block in extracted]
    all_re = re.compile(r'^(all\s*:)\s*$', re.MULTILINE)
    joined = '\n'.join(out)
    if hoisted_names:
        joined = all_re.sub(r'all: ' + ' '.join(hoisted_names), joined, count=1)

    for block in extracted:
        joined += '\n\n' + '\n'.join(block)

    Path(f).write_text(joined + '\n')
    return True


_COMPILE_IN_RECIPE_RE = re.compile(
    r'^\t.*\b(gcc|clang|cc|g\+\+|clang\+\+)\b.*\s-o\s+(\S+)', re.MULTILINE
)


def fix_binary_target_runs_itself(f: str) -> bool:
    """Fix a binary target whose recipe runs the binary instead of compiling it.

    Pattern: target ``X:`` with a recipe line that is just ``X`` or ``./X``
    (running the binary, not compiling it), while some other target (e.g. ``all:``)
    holds the actual compile recipe ``cc -o X ...``.  The fix swaps them: the
    compile command moves into ``X:`` and the other target's recipe is cleared so
    it just declares the dependency.

    This is a general-class error — any C/C++ project can exhibit it when the
    model confuses the binary target with a run command.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False

    # Parse into blocks: each block = [header_line, *recipe_lines]
    lines = content.splitlines()
    top_re = re.compile(r'^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:')
    blocks: list[tuple[int, str, list[str]]] = []  # (line_idx, name, recipe_lines)
    i = 0
    while i < len(lines):
        m = top_re.match(lines[i])
        if m and lines[i][0] not in (' ', '\t'):
            name = m.group(1)
            recipe: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].startswith('\t'):
                recipe.append(lines[j])
                j += 1
            blocks.append((i, name, recipe))
            i = j
        else:
            i += 1

    # Find a target X whose sole recipe runs X (bare name or ./X).
    bad_target: tuple[int, str, list[str]] | None = None
    for idx, name, recipe in blocks:
        non_empty = [r.strip() for r in recipe if r.strip()]
        if len(non_empty) == 1 and non_empty[0] in (name, './' + name):
            bad_target = (idx, name, recipe)
            break
    if bad_target is None:
        return False

    _, binary, _ = bad_target

    # Find a compile recipe for `binary` in another target.
    compile_src_idx: int | None = None
    compile_line: str | None = None
    for idx, name, recipe in blocks:
        if name == binary:
            continue
        for r in recipe:
            m2 = re.match(r'^\t.*\b(gcc|clang|cc|g\+\+|clang\+\+)\b.*\s-o\s+' +
                          re.escape(binary) + r'\b', r)
            if m2:
                compile_src_idx = idx
                compile_line = r
                break
        if compile_line:
            break
    if compile_line is None:
        return False

    # Rebuild: put compile_line into binary: and remove it from the source target.
    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = top_re.match(line)
        if m and line[0] not in (' ', '\t'):
            name = m.group(1)
            new_lines.append(line)
            i += 1
            # Collect recipe
            recipe_start = i
            while i < len(lines) and lines[i].startswith('\t'):
                i += 1
            recipe_lines = lines[recipe_start:i]
            if name == binary:
                # Replace run-self recipe with compile command
                new_lines.append(compile_line)
            elif recipe_start - 1 == compile_src_idx:
                # Remove just the compile line from this target's recipe
                new_lines.extend(r for r in recipe_lines if r != compile_line)
            else:
                new_lines.extend(recipe_lines)
        else:
            new_lines.append(line)
            i += 1

    result = '\n'.join(new_lines)
    if result == content:
        return False
    Path(f).write_text(result)
    return True


def fix_duplicate_var(f: str) -> bool:
    """Remove duplicate top-level variable assignments (keep first)."""
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    var_re = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*[?:+]?=')
    lines, seen, changed, out = data.splitlines(), set(), False, []
    for line in lines:
        m = var_re.match(line)
        if m:
            if m.group(1) in seen:
                changed = True
                continue
            seen.add(m.group(1))
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True


# ── Go reflexes ───────────────────────────────────────────────────────────────

def fix_python_venv_cmd(f: str) -> bool:
    """Replace bare 'python' with 'python3' in Makefile venv/pip recipes.

    On macOS and many Linux systems, 'python' is absent or points to Python 2.
    The canonical command is 'python3'.  Only applies inside recipe lines
    (tab-indented) to avoid touching variable assignments or comments.
    """
    if shutil.which('python') and not shutil.which('python3'):
        return False  # system has python but not python3 — no change needed
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    _PY_CMD_RE = re.compile(r'(?m)^(\t.*\b)python( )')
    new_content = _PY_CMD_RE.sub(r'\1python3\2', content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    return True




def fix_makefile_npm_test_jest(f: str) -> bool:
    """Replace `npm test` with `npx jest --forceExit` when jest is a devDependency.

    Models write `npm test` in Makefile recipes which delegates to the
    package.json test script (`"test": "jest"`). Bare `jest` in a shell
    script is not on PATH; only the npx-resolved binary in node_modules/.bin
    works. Generic: applies to any Node.js project with jest as a dep.
    """
    if not Path(f).name.lower() == 'makefile':
        return False
    pkg = Path(f).parent / 'package.json'
    if not pkg.exists():
        return False
    try:
        import json as _json
        deps = _json.loads(pkg.read_text())
        all_deps = {**deps.get('dependencies', {}), **deps.get('devDependencies', {})}
    except Exception:
        return False
    if 'jest' not in all_deps:
        return False
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    new_content = re.sub(r'(?m)^(\t.*)npm test\b', r'\1npx jest --forceExit', content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced npm test with npx jest in {f}")
    return True






def fix_makefile_escaped_dollar(f: str) -> bool:
    r"""Replace \$(cmd) patterns in Makefile recipes with $(cmd) or bare cmd.

    Models sometimes write `\$(npm) install` thinking it calls npm. In a
    Makefile recipe `\$` means a literal `$`, so the shell receives `$(npm)
    install` where `$(npm)` is a command-substitution — empty for npm — leaving
    just ` install` which fails. Replace `\$(npm)` with `npm`, `\$(node)` with
    `node`, `\$(python)` with `python3`, and `\$(make)` with `$(MAKE)`.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if r'\$(' not in content:
        return False
    replacements = {
        r'\$(npm)': 'npm',
        r'\$(node)': 'node',
        r'\$(python3)': 'python3',
        r'\$(python)': 'python3',
        r'\$(make)': '$(MAKE)',
        r'\$(cargo)': 'cargo',
        r'\$(go)': 'go',
    }
    new_content = content
    for bad, good in replacements.items():
        new_content = new_content.replace(bad, good)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced escaped \\$(...) with direct commands in {f}")
    return True


def fix_makefile_pytest_in_non_python(f: str) -> bool:
    """Replace 'pytest' in test: target when the project has no Python source files.

    When a model writes a C/Rust/Go Makefile but still puts 'pytest' in the
    test: recipe, 'make' fails immediately. If no .py files exist in the project
    directory, replace the pytest call with '@true' (no-op) so make succeeds.
    Also removes 'test' from the default target's prerequisites to avoid running
    pytest as a build step.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Only fire if the Makefile has a test: target with pytest
    if not re.search(r'(?m)^test\s*:.*\n\t.*pytest\b', content):
        return False
    # Don't touch Python projects
    proj_dir = Path(f).parent
    if list(proj_dir.glob('*.py')) or list(proj_dir.glob('requirements.txt')):
        return False
    # Replace pytest in test: recipe with @true (no-op)
    new_content = re.sub(
        r'(?m)^(test\s*:.*\n)(\t.*)pytest\b(.*)',
        r'\1\2@true\3',
        content,
    )
    if new_content == content:
        return False
    # Also remove 'clean' from build target prerequisite lists so the binary
    # isn't deleted before the test command runs './binary'.
    # Pattern: 'target: ... clean ...' → remove 'clean' word from prereqs
    new_content = re.sub(
        r'(?m)^([A-Za-z_][A-Za-z_0-9]*\s*:[^#\n]*)\bclean\b\s*',
        r'\1',
        new_content,
    )
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced pytest in test: target with @true in {f}")
    return True


def fix_makefile_bare_pytest(f: str) -> bool:
    """Replace bare 'pytest' with '.venv/bin/pytest' in Makefile recipes that use a venv.

    When a Makefile creates a .venv for the project, test recipes must use
    .venv/bin/pytest — bare 'pytest' uses the system pytest which lacks the
    installed packages, producing ModuleNotFoundError at collection time.
    Only rewrites when the Makefile already references .venv (install step
    creates it), to avoid changing Makefiles that intentionally use system pytest.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if '.venv' not in content:
        return False
    # Only replace bare 'pytest' — skip lines that already have .venv/bin/pytest
    # or that contain a package manager command (pip install pytest).
    pattern = re.compile(r'(?m)^(\t(?!.*\.venv/bin/)(?!.*\bpip\b).*\b)pytest(\b)')
    new_content = pattern.sub(r'\1.venv/bin/pytest\2', content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced bare pytest with .venv/bin/pytest in {f}")
    return True


def fix_makefile_pip_no_venv(f: str) -> bool:
    """Rewrite Makefiles that do bare 'pip install' then bare 'pytest' to use a venv.

    'pip install -r requirements.txt && pytest' installs packages into whichever
    Python owns the current pip, but 'pytest' may use a different interpreter.
    This produces ModuleNotFoundError at collection. The fix: replace the install
    recipe with a .venv-based pattern and rewrite bare 'pytest' to '.venv/bin/pytest'.
    Only fires when the Makefile has pip install AND bare pytest AND no venv yet.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    has_pip = bool(re.search(r'(?m)^\t.*\bpip\b.*install\b', data))
    has_bare_pytest = bool(re.search(r'(?m)^\t.*(?<!\/)pytest\b', data))
    has_venv = '.venv' in data
    if not (has_pip and has_bare_pytest) or has_venv:
        return False

    # Replace bare `pip` with `.venv/bin/pip` and bare `pytest` with `.venv/bin/pytest`
    new_data = re.sub(r'(?m)^(\t.*)\bpip\b', r'\1.venv/bin/pip', data)
    new_data = re.sub(r'(?m)^(\t.*)(?<!\/)pytest\b', r'\1.venv/bin/pytest', new_data)

    # Insert venv creation before the first recipe that uses pip/pytest
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    pip_install = (f'\t.venv/bin/pip install -r {req_file} pytest'
                   if req_file else '\t.venv/bin/pip install pytest')
    venv_block = f'\n.venv:\n\tpython3 -m venv .venv\n{pip_install}\n'

    # Add .venv as prerequisite of targets that now reference .venv/bin/
    top_re = re.compile(r'(?m)^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:([^=\n]*)$')
    def add_venv_dep(m):
        name, prereqs = m.group(1), m.group(2).strip()
        if name == '.venv':
            return m.group(0)
        return f'{name}: .venv {prereqs}'.rstrip()
    new_data = top_re.sub(add_venv_dep, new_data)
    new_data += venv_block

    Path(f).write_text(new_data)
    print(f"==> [mu-agent] Reflex: rewrote Makefile to use .venv in {f}")
    return True


def fix_makefile_pip_install_empty(f: str) -> bool:
    """Replace bare `pip install` (no packages, no -r) in Makefile recipes.

    Models sometimes write `.venv/bin/pip install ` or `pip install ` with no
    arguments or just whitespace. This raises "You must give at least one
    requirement to install". If a requirements.txt exists, replace with
    `pip install -r requirements.txt`; otherwise add `pytest` as a fallback.
    General: any pip install with no arguments will fail.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    # Match tab-indented pip install lines that have nothing meaningful after 'install'
    pattern = re.compile(r'(?m)^(\t[^\n]*pip\s+install)\s*$')
    if not pattern.search(data):
        return False
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    if req_file:
        replacement = rf'\1 -r {req_file}'
    else:
        replacement = r'\1 pytest'
    new_data = pattern.sub(replacement, data)
    if new_data == data:
        return False
    Path(f).write_text(new_data)
    print(f"==> [mu-agent] Reflex: added package args to bare pip install in {f}")
    return True


def fix_missing_venv_rule(f: str) -> bool:
    """Add a .venv setup rule when Makefile uses .venv/bin/X but has no .venv: rule.

    A Makefile that calls `.venv/bin/pytest` (or any `.venv/bin/X`) in a
    recipe fails with 'No such file or directory' unless some target creates
    the virtualenv first.  This reflex inserts a `.venv:` target (python3 -m
    venv + pip install) and makes every target that uses .venv/bin depend on it.

    General rule: if you reference a generated directory path in a recipe, you
    must also have a rule that builds it.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False

    if '.venv/bin/' not in data:
        return False

    # Check if there's already a rule for .venv
    if re.search(r'(?m)^\.venv\s*:', data):
        return False

    lines = data.splitlines()

    # Find which targets reference .venv/bin/ — add .venv as a prerequisite
    top_re = re.compile(r'^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:([^=]*)$')
    changed_targets: list[str] = []
    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = top_re.match(line)
        if m and line[0] not in (' ', '\t'):
            name, prereqs = m.group(1), m.group(2).strip()
            # Look ahead at recipe to see if it uses .venv/bin/
            j = i + 1
            uses_venv = False
            while j < len(lines) and lines[j].startswith('\t'):
                if '.venv/bin/' in lines[j]:
                    uses_venv = True
                j += 1
            if uses_venv and '.venv' not in prereqs:
                deps = ('.venv ' + prereqs).strip()
                new_lines.append(f'{name}: {deps}')
                changed_targets.append(name)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
        i += 1

    # Determine requirements file to install
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    pip_install = (f'\t.venv/bin/pip install -r {req_file} pytest'
                   if req_file else '\t.venv/bin/pip install pytest')
    venv_block = [
        '',
        '.venv:',
        '\tpython3 -m venv .venv',
        pip_install,
    ]
    new_lines.extend(venv_block)

    Path(f).write_text('\n'.join(new_lines) + '\n')
    return True


def fix_makefile_literal_tab_escape(f: str) -> bool:
    """Remove/replace literal \\t and \\@ escape sequences in Makefiles.

    Models sometimes write \\t (backslash + t) thinking it means TAB, and \\@
    thinking it silences a recipe line. In Makefiles these are literal characters.

    Cases handled:
    - Line starts with \\t: replace with real TAB (recipe indentation).
    - Line starts with \\@: replace with real TAB + @ (silent recipe).
    - \\t inside a variable or recipe line: replace with space.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    if '\\t' not in text and '\\@' not in text:
        return False
    lines = text.splitlines()
    changed = False
    out = []
    for line in lines:
        if line.startswith('\\@'):
            out.append('\t@' + line[2:])
            changed = True
        elif line.startswith('\\t'):
            out.append('\t' + line[2:])
            changed = True
        elif line.startswith('\t\\@'):
            # Real tab followed by \@ — convert \@ to @ (already has proper indent)
            out.append('\t@' + line[3:])
            changed = True
        elif '\\t' in line:
            new_line = line.replace('\\t', ' ')
            out.append(new_line)
            changed = True
        else:
            out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: removed literal \\t escape(s) in {f}")
    return True


def fix_makefile_literal_newline_escape(f: str) -> bool:
    """Replace literal \\n escape sequences in Makefiles with real newlines.

    Models emit \\n (backslash + n) thinking it means a line break. Strategy:
    \\n\\n → blank line (target boundary), \\n → newline+tab (recipe line).
    After substitution, repair any target-like bare words (no colon, no tab)
    that should be target declarations.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    if '\\n' not in text:
        return False
    new_text = text.replace('\\n\\n', '\n\n')
    new_text = new_text.replace('\\n', '\n\t')
    # Post-pass: fix lines that look like targets missing their colon.
    # A target line has no leading whitespace, a word, and no colon.
    lines = new_text.splitlines()
    result = []
    for ln in lines:
        if ln == '\t':          # lone-tab empty continuation — skip
            continue
        # Bare word at column 0, not a comment, not blank, no colon → add ':'
        if (ln and not ln[0].isspace() and not ln.startswith('#')
                and ':' not in ln and re.match(r'^[A-Za-z_][\w-]*$', ln.strip())):
            ln = ln.rstrip() + ':'
        result.append(ln)
    new_text = '\n'.join(result)
    if new_text == text:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced literal \\n escape(s) in {f}")
    return True


def fix_makefile_binary_name(f: str, test_cmd: str) -> bool:
    """Rename the Makefile's output binary to match what the test command expects.

    When the test command is `make && ./foo` but the Makefile builds `bar`, the
    compiled binary exists but the test can't find it. This reflex renames the
    Makefile target and -o flag to match the expected binary name.
    General: applies to any compiled-language Makefile, not SDL2-specific.
    """
    if not test_cmd:
        return False
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Extract expected binary from test command: `./name` or bare `name` after `make &&`
    m = re.search(r'&&\s+\.?/?([\w.-]+)\s*$', test_cmd)
    if not m:
        return False
    expected = m.group(1)
    # Find the actual -o target in the Makefile
    o_match = re.search(r'-o\s+([\w.-]+)', text)
    if not o_match:
        return False
    actual = o_match.group(1)
    if actual == expected:
        return False
    # Rename: replace all occurrences of the actual binary name as a whole word
    new_text = re.sub(rf'\b{re.escape(actual)}\b', expected, text)
    if new_text == text:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: renamed Makefile binary '{actual}' → '{expected}' in {f}")
    return True


def fix_makefile_wrong_c_compiler(f: str) -> bool:
    """Replace bare 'c ' as compiler with 'cc ' in Makefile recipe lines.

    Models occasionally write `c $(CFLAGS)` or `c -o binary main.c` where
    `c` is not a valid compiler name (should be `cc` or `clang`). This only
    fires when the recipe line starts with TAB + `c ` followed by typical
    compile flags (-o, -I, -L, -l, $(CC), $(CFLAGS)).
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    pattern = re.compile(r'(?m)^(\t)c +(?=-[oILl]|\$\()')
    new_text, count = pattern.subn(r'\1cc ', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced bare 'c' compiler with 'cc' in {f}")
    return True


def fix_makefile_double_colon_target(f: str) -> bool:
    """Fix lines with two colons that make misreads as a static pattern rule.

    `target pattern contains no '%'` means Make saw `A: B: C` and treated
    B as a target pattern. This happens when a model writes the prerequisite
    and recipe on the same target line separated by an extra colon:
        hello_world: main.c: cc -o hello_world main.c
    Fix: strip everything after the second colon and move it to the next line
    as a tab-indented recipe.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    changed = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or line.startswith('\t'):
            out.append(line)
            continue
        # Count colons outside of shell expansions $(...)
        parts = stripped.split(':')
        if len(parts) >= 3 and not stripped.startswith('.'):
            target = parts[0].strip()
            prereq = parts[1].strip()
            recipe = ':'.join(parts[2:]).strip()
            if recipe and not recipe.startswith('='):
                out.append(f'{target}: {prereq}')
                out.append(f'\t{recipe}')
                changed = True
                continue
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: fixed double-colon target line(s) in {f}")
    return True


def fix_makefile_missing_compile_rule(f: str) -> bool:
    """Add a missing compile rule when all: depends on a binary with no build recipe.

    Pattern: `all: hello_world` exists but no `hello_world:` target. This leaves
    Make unable to build the binary. Adds a minimal `NAME: *.c` rule using the
    source files present in the current directory.
    General: applies to any C project missing a binary target, not hello-world-specific.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Find all declared targets
    declared = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', text, re.MULTILINE))
    # Find all: prerequisites that look like binary names (not source files, not .PHONY)
    all_match = re.search(r'^all\s*:\s*(.+)$', text, re.MULTILINE)
    if not all_match:
        return False
    prereqs = all_match.group(1).split()
    # Bail if the `all:` line is malformed — i.e. any token is not a plausible
    # prerequisite (clean name, source file, or make variable). A line like
    # `all: int main(void) {` means the model spilled code onto it; editing such
    # a Makefile does more harm than good, so leave it for other reflexes/repair.
    _VALID_PREREQ = re.compile(
        r'(?:[A-Za-z_][A-Za-z0-9_-]*|[A-Za-z0-9_./-]+\.[A-Za-z0-9]+|\$[({][A-Za-z_]\w*[)}])$')
    if not all(_VALID_PREREQ.match(p) for p in prereqs):
        return False
    # A real binary target is a clean identifier. This guard rejects:
    #   - make variables ($(TARGET), ${PROG}) — they expand to a name defined
    #     elsewhere, so they are never "missing"; treating them as missing made
    #     this reflex re-append a bogus rule on every repair iteration.
    #   - garbage tokens scraped from a corrupted `all:` line (e.g. `\`,
    #     `main(void)`, `{`) when the model emitted C code or escapes onto it.
    _IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*$')
    missing_binaries = [p for p in prereqs
                        if p not in declared and _IDENT.match(p)]
    if not missing_binaries:
        return False
    # Find C source files to use as dependencies. If there are no .c files this
    # Makefile is not for a C project — don't add a bogus compile rule.
    c_sources = list(Path(f).parent.glob('*.c'))
    if not c_sources:
        return False
    src_dep = ' '.join(s.name for s in c_sources)
    additions = []
    for binary in missing_binaries:
        # Idempotency guard: never append a rule for a binary that already has a
        # `binary:` target. Without this the reflex duplicates the rule each time
        # it runs across repair iterations, wedging the loop on "duplicate edit".
        if re.search(rf'^{re.escape(binary)}\s*:', text, re.MULTILINE):
            continue
        additions.append(f'\n{binary}: {src_dep}')
        additions.append(f'\tcc -o {binary} {src_dep} $(CFLAGS) $(LDFLAGS)')
    if not additions:
        return False
    Path(f).write_text(text.rstrip() + '\n' + '\n'.join(additions) + '\n')
    print(f"==> [mu-agent] Reflex: added missing compile rule(s) for {missing_binaries} in {f}")
    return True


def fix_makefile_sdl2_config_typo(f: str) -> bool:
    """Fix common misspellings of sdl2-config in Makefiles.

    Models occasionally write 'sdl2-cconfig', 'sdl2config', 'SDL2-config', etc.
    The correct tool name is exactly 'sdl2-config'.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Fix common typo variants
    pattern = re.compile(r'\bsdl2-cconfig\b|\bsdl2config\b|\bSDL2-config\b|\bsdl2-Config\b', re.IGNORECASE)
    new_text, count = pattern.subn('sdl2-config', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: fixed sdl2-config typo in {f}")
    return True


def fix_config_tool_redundant_flag(f: str) -> bool:
    """Remove redundant -L / -I flags that immediately precede a $(shell *-config ...)
    expansion whose output already contains those flags.

    A model commonly writes:
        LDFLAGS = -L $(shell sdl2-config --libs)
    which expands to "-L -L/opt/homebrew/lib -lSDL2", causing a bare "-L" with no
    path and a linker failure. The correct form is just:
        LDFLAGS = $(shell sdl2-config --libs)
    This is a general error with any *-config or pkg-config invocation.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Match: -L or -I (with optional space) immediately before $(shell ...-config
    # or pkg-config invocation). Replace the whole match minus the flag.
    pattern = re.compile(
        r'(-[LI])\s+(\$\(shell\s+(?:pkg-config\b|[a-z0-9_-]+-config\b))',
    )
    new_text, count = pattern.subn(r'\2', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed {count} redundant flag(s) before $(shell *-config) in {f}")
    return True


def fix_requirements_path_entries(f: str) -> bool:
    """Remove path-style entries from requirements.txt.

    Models sometimes write executable paths (e.g. '.venv/bin/pytest') into
    requirements.txt instead of package names. pip rejects these with
    'Expected package name at the start of dependency specifier'.
    Any line that starts with '.' or '/' (a path, not a package name) is stripped.
    """
    if not f.endswith('requirements.txt'):
        return False
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    cleaned = [ln for ln in lines if not ln.lstrip().startswith(('.', '/'))]
    if len(cleaned) == len(lines):
        return False
    Path(f).write_text(''.join(cleaned))
    print(f"==> [mu-agent] Reflex: removed {len(lines) - len(cleaned)} path entry/entries from {f}")
    return True


def fix_makefile_recipe_is_prerequisite_list(f: str) -> bool:
    """Fix a target whose recipe line consists solely of declared target names.

    When `all:` has a recipe `\tinstall test` instead of prerequisites
    `all: install test`, make executes `install test` as a shell command, which
    fails because `install` is a real POSIX binary unrelated to the Makefile.
    This reflex detects recipe lines made up entirely of words that are
    declared targets and converts them to prerequisites on the target line.
    General: applies to any Makefile with this structural mistake.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Find all declared target names.
    declared = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', content, re.MULTILINE))
    if not declared:
        return False
    # Scan each target: if it has no prerequisites and its FIRST recipe line
    # consists entirely of declared target names, promote them to prerequisites.
    top_re = re.compile(r'^([A-Za-z0-9_.-]+)\s*:\s*$', re.MULTILINE)
    lines = content.splitlines(keepends=True)
    changed = False
    result = []
    i = 0
    while i < len(lines):
        m = top_re.match(lines[i])
        if m:
            target = m.group(1)
            # Peek at the next (recipe) line.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith('\t'):
                recipe = lines[j].strip()
                words = recipe.split()
                # All words must be declared targets AND there must be >0 words.
                known = declared | _KNOWN_TARGETS
                if words and all(w in known for w in words) and words != [target]:
                    # Replace the target line with prerequisites and remove recipe.
                    result.append(f'{target}: {recipe}\n')
                    i += 1  # skip old target line
                    # Skip blank lines
                    while i < len(lines) and not lines[i].strip():
                        result.append(lines[i])
                        i += 1
                    # Skip the recipe line we just promoted.
                    if i < len(lines) and lines[i].startswith('\t'):
                        i += 1
                    changed = True
                    continue
        result.append(lines[i])
        i += 1
    if not changed:
        return False
    Path(f).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: promoted recipe to prerequisites in {f}")
    return True


def fix_makefile_bare_vitest(f: str) -> bool:
    """Replace bare `vitest` recipe commands with `npx vitest run`.

    vitest is a project-local binary in node_modules/.bin — calling it directly
    in a Makefile recipe fails because it's not on PATH. `npx vitest run` finds
    it in node_modules and runs in non-watch (single-pass) mode.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Match tab-indented lines with `vitest` or `vitest run` not already prefixed with `npx`
    # First handle `vitest run` -> `npx vitest run` (no double 'run')
    new_content = re.sub(
        r'(?m)^(\t[^\n]*)(?<!npx )\bvitest\s+run\b',
        lambda m: m.group(0).replace('vitest run', 'npx vitest run', 1),
        content,
    )
    # Then handle bare `vitest` (not followed by `run` and not preceded by `npx`)
    new_content = re.sub(
        r'(?m)^(\t[^\n]*)(?<!npx )\bvitest\b(?!\s+run\b)(?!\s*:)',
        lambda m: re.sub(r'\bvitest\b(?!\s+run\b)', 'npx vitest run', m.group(0)),
        new_content,
    )
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced bare vitest with npx vitest run in {f}")
    return True


# Makefile reflexes, ordered by concern so the chain flows from coarse structure
# to fine details. The fixpoint runner re-applies the whole chain until stable,
# so this order need only be *roughly* right — a later reflex enabling an earlier
# one is handled by the next pass, and the cycle guard catches any contradiction.
#   1. de-noise raw text artifacts (escapes, tool-call litter)
#   2. structural repair (indentation, nested/orphan targets, missing rules)
#   3. recipe/command correctness (venv, pytest, jest, vitest, flags)
_MAKEFILE_REFLEXES = [
    # 1. text artifacts
    fix_tool_call_artifacts,
    fix_makefile_literal_tab_escape, fix_makefile_literal_newline_escape,
    fix_makefile_escaped_dollar, fix_makefile_backslash_artifact,
    fix_makefile_wrong_c_compiler, fix_makefile_sdl2_config_typo,
    # 2. structure
    fix_makefile_double_colon_target,
    fix_makefile_space_indent, fix_nested_targets,
    fix_orphan_top_level_commands, fix_no_targets,
    fix_inline_recipe, fix_binary_target_runs_itself,
    fix_makefile_missing_compile_rule,
    fix_makefile_recipe_is_prerequisite_list,
    # 3. recipe/command correctness
    fix_duplicate_var, fix_python_venv_cmd, fix_makefile_pip_no_venv,
    fix_makefile_pip_install_empty, fix_makefile_pytest_in_non_python,
    fix_makefile_bare_pytest, fix_makefile_npm_test_jest, fix_makefile_bare_vitest,
    fix_missing_venv_rule, fix_config_tool_redundant_flag,
]


def apply_makefile_reflexes(f: str) -> None:
    run_reflexes(_MAKEFILE_REFLEXES, f)


# ── Plan reflexes ─────────────────────────────────────────────────────────────
# Deterministic clarifications applied to PLAN.md task descriptions, derived from
# the failure modes a weak model repeatedly makes (the same knowledge the write-
# time skills carry). They enrich the spec the writer sees WITHOUT adding,
# removing, or renaming tasks — turning "the dojo surfaces a failure" into "the
# plan states the contract up front". This is the honest, decompose-free form of
# `mu improve-plan`.

# Pending-task lines only (`- [ ] path …`); done/in-progress tasks are untouched.
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
