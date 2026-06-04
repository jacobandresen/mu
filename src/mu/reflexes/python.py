"""Python reflexes: deterministic post-write fixers for Python sources — syntax
repair, project/stdlib import insertion, SQLite test-isolation, Flask route/test
fixes, and requirements.txt/pip hygiene. Split out of the monolithic reflexes
module so each language's fixers live together. No logic changes from the
original.
"""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path


__all__ = [
    'fix_multiline_single_quote',
    'fix_missing_close_paren',
    'fix_test_import_module',
    'py_autofix',
    'fix_python_missing_project_imports',
    'fix_python_undefined_imports',
    'fix_sqlite_test_isolation',
    'fix_sqlite_memory_multi_connect',
    'fix_sqlite_path_unlink',
    'fix_python_missing_stdlib_imports',
    'fix_requirements_stdlib_entries',
    'fix_missing_pip_packages',
    'fix_python_method_indent',
    'fix_python_decorator_colon',
    'fix_python_missing_def',
    'fix_sqlite_missing_row_factory',
    'fix_flask_post_missing_201',
    'fix_flask_test_route_decorators',
    'fix_flask_init_db_import',
    'fix_missing_flask_client_fixture',
    'fix_requirements_path_entries',
]


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
    """Return {stem: source} for non-test .py modules importable beside file_path.

    Looks in the file's own directory and, when it sits in a ``tests``/``test``
    subdirectory, the parent (project root) too — the standard pytest layout is
    ``root/main.py`` + ``root/tests/test_main.py``, where the implementation
    module a test needs to import lives one level up, not beside the test. Closer
    directories win on a stem clash.
    """
    fp = Path(file_path)
    dirs = [fp.parent]
    if fp.parent.name.lower() in ('tests', 'test'):
        dirs.append(fp.parent.parent)
    sources: dict[str, str] = {}
    for d in dirs:
        for p in d.glob('*.py'):
            if p.stem == fp.stem or p.stem.startswith('test_') or p.stem in sources:
                continue
            try:
                sources[p.stem] = p.read_text()
            except OSError:
                continue
    return sources

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
    """Add imports for names reported undefined, by linter OR runtime evidence.

    Recognizes two forms of the same class of error — a name used but never
    imported or defined:
      * pyflakes/flake8 lint:  ``undefined name 'X'`` (F821/F811)
      * Python runtime/pytest: ``NameError: name 'X' is not defined``
    The runtime form matters because a test that uses ``app``/``db`` from the
    implementation module passes a syntax-only lint gate and only fails when
    pytest runs it, so the lint-phase resolver never sees it. For each undefined
    name it searches sibling .py files for a top-level assignment, class, or
    function defining X and adds ``from <module> import X``. Generic: driven
    entirely by the error text and file contents, not any specific problem.
    """
    if not file_path.lower().endswith('.py'):
        return False
    undefined = set(re.findall(r"undefined name '(\w+)'", lint_error))
    undefined |= set(re.findall(r"NameError: name '(\w+)' is not defined", lint_error))
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
