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

import json
import re
import shutil
import subprocess
from pathlib import Path

_TARGET_RE = re.compile(r'(?m)^[a-zA-Z_.][a-zA-Z0-9._-]*\s*:')
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


def fix_c_sdl_header(file_path: str) -> bool:
    """Fix wrong SDL2 include path in C files.

    `#include <SDL.h>` does not exist on macOS/Linux SDL2 installs — the
    correct header is `#include <SDL2/SDL.h>`. Also fixes SDL_image, SDL_ttf etc.
    General: applies to any C/C++ file using SDL2.
    """
    if not file_path.lower().endswith(('.c', '.cpp', '.cc', '.h')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Fix <SDL.h> → <SDL2/SDL.h>, <SDL_image.h> → <SDL2/SDL_image.h>, etc.
    pattern = re.compile(r'#include\s*<(SDL[^2/][^>]*)>')
    new_text, count = pattern.subn(r'#include <SDL2/\1>', text)
    if not count:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: fixed SDL include path(s) in {file_path}")
    return True


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


def fix_rust_println_missing_arg(file_path: str) -> bool:
    """Fix println!/print! calls whose placeholder count doesn't match argument count.

    Models write format strings like `println!("{}")` or `println!("Fib({}) = {}")`
    with too few arguments. When inside a `for var in ...` loop, fills missing args
    with the loop variable (repeated if needed). Generic: any mismatch between `{}`
    count and argument count is a compile error in Rust.
    """
    if not file_path.endswith('.rs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    changed = False
    result = []
    loop_var_stack: list[str] = []

    for line in lines:
        stripped = line.strip()
        m = re.match(r'for\s+(\w+)\s+in\b', stripped)
        if m:
            loop_var_stack.append(m.group(1))

        # Match println!("...") or print!("...") — capture format string and args
        macro_m = re.search(r'\b(println|print)!\s*\(("(?:[^"\\]|\\.)*")(.*)\)', line)
        if macro_m:
            fmt_str = macro_m.group(2)  # includes surrounding quotes
            rest = macro_m.group(3)     # ', arg1, arg2, ...' or ''
            n_placeholders = fmt_str.count('{}')
            existing_args = [a.strip() for a in rest.lstrip(',').split(',') if a.strip()]
            if n_placeholders > len(existing_args) and loop_var_stack:
                var = loop_var_stack[-1]
                all_args = existing_args + [var] * (n_placeholders - len(existing_args))
                new_call = f'{macro_m.group(1)}!({fmt_str}, {", ".join(all_args)})'
                line = line.replace(macro_m.group(0), new_call, 1)
                changed = True

        if stripped == '}' and loop_var_stack:
            loop_var_stack.pop()
        result.append(line)

    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: fixed println! missing arg(s) in {file_path}")
    return True


def fix_rust_cargo_toml(file_path: str) -> bool:
    """Regenerate a corrupted Cargo.toml that has merged or duplicate sections.

    The repair model sometimes appends content to Cargo.toml without proper
    separation, producing artifacts like `authors = ["x"][package]` or multiple
    `[package]` headers. Detect these and replace with a minimal valid Cargo.toml.
    """
    if Path(file_path).name.lower() != 'cargo.toml':
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Corruption signals: inline '][', multiple [package] sections, [[package]]
    is_corrupt = (
        re.search(r'\]\[', text) is not None
        or text.count('\n[package]') > 1
        or '[[package]]' in text
        or text.count('[package]') > 1
    )
    if not is_corrupt:
        return False
    # Extract the project name if we can find it
    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    proj = m.group(1) if m else Path(file_path).parent.name or 'app'
    # Detect if there's a src/main.rs or main.rs to set up [[bin]]
    has_src_main = Path(Path(file_path).parent / 'src' / 'main.rs').exists()
    has_root_main = Path(Path(file_path).parent / 'main.rs').exists()
    clean = (
        '[package]\n'
        f'name = "{proj}"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
    )
    if has_root_main and not has_src_main:
        clean += f'\n[[bin]]\nname = "{proj}"\npath = "main.rs"\n'
    Path(file_path).write_text(clean)
    print(f"==> [mu-agent] Reflex: regenerated corrupted Cargo.toml in {file_path}")
    return True


def fix_rust_duplicate_use(file_path: str) -> bool:
    """Remove exact duplicate `use` lines from a Rust source file.

    The model sometimes emits the same `use std::io::{self, Write};` line twice,
    causing E0252 'name defined multiple times'. Dedup in order of first occurrence.
    """
    if not file_path.endswith('.rs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    seen: set[str] = set()
    result = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('use ') and stripped in seen:
            changed = True
            continue
        if stripped.startswith('use '):
            seen.add(stripped)
        result.append(line)
    if not changed:
        return False
    Path(file_path).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: removed duplicate use statement(s) in {file_path}")
    return True


def fix_csharp_undefined_types(file_path: str, test_output: str) -> bool:
    """Replace undefined C# type names with ones defined in sibling .cs files.

    CS0246 'type not found' means the file references a class/struct that doesn't
    exist in the project. This often happens when the model uses placeholder names
    from example code (e.g. `Item` instead of `Post`). The reflex looks for types
    named in CS0246 errors, finds the actual type names in sibling .cs files, and
    renames them. General: applies to any C# project with a type naming mismatch.
    """
    if not file_path.endswith('.cs'):
        return False
    if 'CS0246' not in test_output and 'type or namespace name' not in test_output:
        return False
    undefined = re.findall(r"error CS0246: The type or namespace name '(\w+)'", test_output)
    if not undefined:
        return False
    path = Path(file_path)
    try:
        text = path.read_text()
    except OSError:
        return False
    # Collect class/struct/record names from sibling .cs files
    sibling_types: set[str] = set()
    for sib in path.parent.glob('*.cs'):
        if sib == path:
            continue
        try:
            src = sib.read_text()
        except OSError:
            continue
        for m in re.finditer(r'\b(?:class|struct|record)\s+(\w+)', src):
            sibling_types.add(m.group(1))
    if not sibling_types:
        return False
    changed = False
    for undef in undefined:
        if undef in sibling_types:
            continue  # type IS defined — not our problem
        # Find a sibling type whose name is similar (heuristic: contains or starts with similar chars)
        candidates = [t for t in sibling_types if (
            undef.lower() in t.lower() or t.lower() in undef.lower() or
            undef[:3].lower() == t[:3].lower()
        )]
        if not candidates:
            continue
        # Pick the shortest candidate (most likely to be the base model type)
        replacement = min(candidates, key=len)
        new_text = re.sub(rf'\b{re.escape(undef)}\b', replacement, text)
        if new_text != text:
            text = new_text
            changed = True
            print(f"==> [mu-agent] Reflex: renamed undefined type '{undef}' → '{replacement}' in {file_path}")
    if not changed:
        return False
    path.write_text(text)
    return True


def fix_csharp_app_used_before_declared(file_path: str, test_output: str = '') -> bool:
    """Fix C# Program.cs where `app` is used before `var app = builder.Build()`.

    CS0841 'Cannot use local variable before it is declared' on `app` means the
    model called `app.MapGet(...)` or `app.Run()` before `builder.Build()`. The
    fix: move `var app = builder.Build();` to immediately before the first `app.`
    usage. General: applies to any ASP.NET Core minimal API file with this ordering
    bug, not specific to any dojo task.
    """
    if not file_path.endswith('.cs'):
        return False
    if test_output and 'CS0841' not in test_output and 'before it is declared' not in test_output:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    build_pattern = re.compile(r'^(var\s+app\s*=\s*builder\.Build\(\)\s*;)\s*$', re.MULTILINE)
    app_use_pattern = re.compile(r'^\s*app\.', re.MULTILINE)

    build_match = build_pattern.search(text)
    if not build_match:
        return False

    # Find position of first `app.` usage
    first_use = app_use_pattern.search(text)
    if not first_use:
        return False

    build_pos = build_match.start()
    if build_pos < first_use.start():
        return False  # already in correct order

    # Remove the build line from its current position
    build_line = build_match.group(0)
    new_text = text[:build_match.start()] + text[build_match.end():]
    # Re-find the first app. usage in the modified text
    first_use2 = app_use_pattern.search(new_text)
    if not first_use2:
        return False
    # Insert build line before the first app. usage
    insert_at = first_use2.start()
    # Find the start of that line
    line_start = new_text.rfind('\n', 0, insert_at) + 1
    new_text = new_text[:line_start] + build_line + '\n' + new_text[line_start:]
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: moved 'var app = builder.Build()' before first app. usage in {file_path}")
    return True


def fix_vue_missing_package(project_dir: str) -> bool:
    """Add `vue` to package.json devDependencies when it is missing.

    `@vitejs/plugin-vue` and `@vue/test-utils` both require `vue` as a peer
    dependency. The lean-system retry often writes package.json without the `vue`
    entry, causing MODULE_NOT_FOUND errors at test time. Generic: any project
    that uses vue-related packages needs the core `vue` package.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
    except Exception:
        return False
    dev = data.get('devDependencies', {})
    deps = data.get('dependencies', {})
    needs_vue = any(k.startswith('@vue/') or k == '@vitejs/plugin-vue'
                    for k in list(dev) + list(deps))
    has_vue = 'vue' in dev or 'vue' in deps
    if not needs_vue or has_vue:
        return False
    dev['vue'] = '^3.4.0'
    data['devDependencies'] = dev
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: added missing vue package to {pkg}")
    return True


def fix_csharp_verbatim_string_escape(file_path: str) -> bool:
    """Convert verbatim strings with backslash escapes to regular strings.

    In C# verbatim strings (@"..."), backslash is literal — `\"` does NOT escape
    a quote; it ends the string. Models write `@"{\"key\":value}"` thinking it
    works like a regular string. The fix: drop the `@` prefix so the string
    becomes a regular string where `\"` is valid. The content stays unchanged.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Find @" followed eventually by \" — the verbatim string has invalid escaping.
    # Replace @" with plain " to make it a regular string.
    new_text = re.sub(r'@("(?:[^"\\]|\\.)*")', r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: converted verbatim strings to regular strings in {file_path}")
    return True


def fix_csharp_keyword_prefix_artifacts(file_path: str) -> bool:
    """Remove stray 1-2 char prefix artifacts glued to C# keywords at line start.

    Models occasionally emit `tnamespace`, `#class`, etc. — a lone character
    fused to a keyword. The `t` before `namespace` causes CS1513/CS1022.
    Pattern: line starts with 1-2 lowercase letters OR a non-letter char,
    immediately followed (no space) by a known keyword + word boundary.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    kws = (r'namespace|class|struct|interface|enum|public|private|protected|'
           r'internal|using|static|abstract|sealed|partial|record')
    # Match 1-2 lowercase letters OR one symbol, fused directly to a keyword
    pattern = re.compile(r'^(?:[a-z]{1,2}|[^a-zA-Z\s])(' + kws + r')\b', re.MULTILINE)
    new_text = pattern.sub(r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed keyword prefix artifact(s) in {file_path}")
    return True


def fix_csharp_using_order(file_path: str) -> bool:
    """Move all `using` directives to the top of a C# source file.

    CS1529 'A using clause must precede all other elements' fires when using
    statements appear after top-level statements, namespace blocks, or class
    definitions. This reflex collects all using lines and re-emits them at the
    very start of the file before any non-using content.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    using_lines = [ln for ln in lines if ln.lstrip().startswith('using ')]
    non_using_lines = [ln for ln in lines if not ln.lstrip().startswith('using ')]
    if not using_lines:
        return False
    # Check if any using is already out of order (appears after non-empty non-using)
    first_non_using = next((i for i, ln in enumerate(lines)
                            if not ln.lstrip().startswith('using ') and ln.strip()), None)
    first_using_after = any(
        i > first_non_using
        for i, ln in enumerate(lines)
        if ln.lstrip().startswith('using ')
    ) if first_non_using is not None else False
    if not first_using_after:
        return False
    new_text = ''.join(using_lines) + ''.join(non_using_lines)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: moved using statements to top of {file_path}")
    return True


def fix_csharp_duplicate_classes(file_path: str) -> bool:
    """Remove class/struct definitions from a C# file that are already defined in a sibling file.

    Models sometimes copy a class into Program.cs even though the planner created
    a separate file for it (e.g. FibonacciGenerator.cs). The compiler rejects the
    duplicate with CS0101. Generic: checks sibling .cs files for any class/struct
    name that also appears in this file and removes the duplicate block.
    """
    if not file_path.endswith('.cs'):
        return False
    path = Path(file_path)
    try:
        text = path.read_text()
    except OSError:
        return False
    # Collect class/struct names defined in sibling .cs files
    sibling_names: set[str] = set()
    for sib in path.parent.glob('*.cs'):
        if sib == path:
            continue
        try:
            src = sib.read_text()
        except OSError:
            continue
        for m in re.finditer(r'\b(?:class|struct|record)\s+(\w+)', src):
            sibling_names.add(m.group(1))
    if not sibling_names:
        return False
    # Remove any class/struct block defined in this file that's already in a sibling
    changed = False
    for name in sibling_names:
        pattern = re.compile(
            rf'(?m)^[ \t]*(?:public|internal|private|protected|static|sealed|abstract|partial\s+)*'
            rf'(?:class|struct|record)\s+{re.escape(name)}\b[^{{]*\{{',
        )
        m = pattern.search(text)
        if not m:
            continue
        # Find the matching closing brace via depth tracking.
        start = m.start()
        depth = 0
        end = len(text)
        for i in range(m.end() - 1, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        text = text[:start] + text[end:]
        changed = True
    if not changed:
        return False
    path.write_text(text)
    print(f"==> [mu-agent] Reflex: removed duplicate C# class(es) from {file_path}")
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


def fix_vitest_watch_mode(project_dir: str) -> bool:
    """Replace bare `vitest` with `vitest run` in package.json test scripts.

    `vitest` without arguments starts in watch mode and waits for file changes
    indefinitely, causing the test command to hang. `vitest run` executes once
    and exits with a pass/fail code. This fires whenever package.json uses the
    bare `vitest` command as the test script.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        text = pkg.read_text()
        data = json.loads(text)
    except Exception:
        return False
    scripts = data.get('scripts', {})
    changed = False
    for key in list(scripts):
        val = scripts[key]
        if isinstance(val, str) and re.search(r'\bvitest\b(?!\s+run\b)', val):
            scripts[key] = re.sub(r'\bvitest\b(?!\s+run\b)', 'vitest run', val)
            changed = True
    if not changed:
        return False
    data['scripts'] = scripts
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: changed vitest to vitest run in {pkg}")
    return True


def fix_vitest_globals(project_dir: str, test_output: str) -> bool:
    """Enable Vitest globals when test output reports 'test is not defined'.

    Vitest does not expose test/expect/describe as globals by default. Without
    `globals: true` in vite.config.ts, calling test(...) raises ReferenceError.
    This reflex adds globals: true to the test config block. General: any Vitest
    project that uses bare test() calls needs globals enabled.
    """
    if 'is not defined' not in test_output and 'ReferenceError' not in test_output:
        return False
    if not any(name in test_output for name in ('test', 'expect', 'describe', 'beforeEach', 'it')):
        return False
    config_path = Path(project_dir) / 'vite.config.ts'
    if not config_path.exists():
        config_path = Path(project_dir) / 'vite.config.js'
    if not config_path.exists():
        return False
    try:
        text = config_path.read_text()
    except OSError:
        return False
    if 'globals: true' in text or "globals:true" in text:
        return False
    # Add globals: true inside the test: { ... } block
    new_text = re.sub(
        r'(test\s*:\s*\{)',
        r'\1\n    globals: true,',
        text,
        count=1,
    )
    if new_text == text:
        # No test block found — append a minimal one
        if 'test:' not in text:
            new_text = re.sub(
                r'(export default defineConfig\(\{)',
                r'\1\n  test: { environment: "jsdom", globals: true },',
                text,
                count=1,
            )
    if new_text == text:
        return False
    config_path.write_text(new_text)
    print(f"==> [mu-agent] Reflex: added Vitest globals:true to {config_path}")
    return True


def fix_js_env_data_file(file_path: str) -> bool:
    """Convert module-level process.env file-path constants to getter functions.

    A module-level `const DATA_FILE = process.env.X || 'default'` is captured
    once at load time. Jest's `beforeEach` changes to `process.env.X` have no
    effect — the constant never updates. Converting to a getter function
    `function getDataFile() { return process.env.X || 'default'; }` evaluates
    the env var on every call, enabling per-test isolation with temp files.
    General: applies to any CommonJS file that needs env-var-driven test isolation.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Match: const X = process.env.Y || 'default';
    m = re.search(
        r'^(const\s+(\w+)\s*=\s*process\.env\.(\w+)\s*\|\|\s*[\'"][^\'"]+[\'"])\s*;',
        text, re.MULTILINE,
    )
    if not m:
        return False
    const_line, var_name = m.group(1) + ';', m.group(2)
    full_expr = m.group(1).split('=', 1)[1].strip()  # process.env.Y || 'default'
    # Skip if this is already inside a function (indented)
    line_start = text.rfind('\n', 0, m.start()) + 1
    if text[line_start:m.start()].strip():
        return False  # indented — already inside a block
    # Skip if it's a test file (test files shouldn't define the data source)
    stem = Path(file_path).stem.lower()
    if stem.startswith('test_') or stem.endswith('_test') or stem.endswith('.test'):
        return False
    # Convert SCREAMING_SNAKE to camelCase getter: DATA_FILE → getDataFile
    parts = var_name.split('_')
    camel = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
    getter_name = 'get' + camel[0].upper() + camel[1:]
    getter_fn = f'function {getter_name}() {{ return {full_expr}; }}'
    # Replace the const declaration with the getter function
    new_text = text.replace(const_line, getter_fn, 1)
    # Replace all remaining usages of the variable with the getter call
    new_text = re.sub(rf'\b{re.escape(var_name)}\b', f'{getter_name}()', new_text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: converted {var_name} to {getter_name}() in {file_path}")
    return True


_JS_NODE_BUILTINS: dict[str, str] = {
    'path': "const path = require('path');",
    'os': "const os = require('os');",
    'fs': "const fs = require('fs');",
    'crypto': "const crypto = require('crypto');",
    'url': "const url = require('url');",
    'http': "const http = require('http');",
    'https': "const https = require('https');",
    'util': "const util = require('util');",
    'assert': "const assert = require('assert');",
    'events': "const events = require('events');",
    'stream': "const stream = require('stream');",
    'child_process': "const child_process = require('child_process');",
}

# Patterns that indicate a module is being used (mod.method or mod[...)
_JS_MODULE_USE_RE = {
    mod: re.compile(rf'\b{re.escape(mod)}\s*\.')
    for mod in _JS_NODE_BUILTINS
}


def fix_js_missing_requires(file_path: str) -> bool:
    """Add missing Node.js built-in require() calls to CommonJS JS files.

    Models often use `path.join()`, `os.tmpdir()`, `fs.readFileSync()` etc.
    without the corresponding `require()` at the top of the file, causing
    `ReferenceError: path is not defined` at runtime. Detects usage via
    `module.method` patterns and adds the missing require statements.
    General: applies to any CommonJS Node.js file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Skip ESM files (import/export syntax)
    if re.search(r'^\s*(?:import|export)\s', text, re.MULTILINE):
        return False
    to_add = []
    for mod, stmt in _JS_NODE_BUILTINS.items():
        if re.search(rf'require\([\'\"]{re.escape(mod)}[\'\"]\)', text):
            continue  # already required
        if _JS_MODULE_USE_RE[mod].search(text):
            to_add.append(stmt)
    if not to_add:
        return False
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('const ') and 'require(' in stripped:
            insert_at = i + 1
        elif stripped and not stripped.startswith('//') and not stripped.startswith('/*') \
                and insert_at > 0:
            break
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing Node.js require(s) to {file_path}")
    return True


def fix_js_extra_closing_brace(file_path: str, test_output: str = '') -> bool:
    """Fix unbalanced braces in JS/TS files when the parser reports a mismatch.

    esbuild / Vitest reports `Unexpected "}"` when a .ts/.js file has more `}`
    than `{`, or `Expected "}" but found ")"` when the reverse is true. This
    reflex counts braces (ignoring strings, template literals, and comments)
    and either removes trailing `}` lines (extra braces) or appends missing
    `}` characters (missing braces). General: applies to any JS/TS file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.ts', '.tsx', '.js', '.jsx'):
        return False
    if test_output and not any(s in test_output for s in
                               ('Unexpected', 'SyntaxError', 'Expected "}"', 'Transform failed')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Count braces AND parens outside strings/comments
    depth = 0  # { vs }
    paren_depth = 0  # ( vs )
    i = 0
    while i < len(text):
        c = text[i]
        # Skip single-line comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        # Skip block comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        # Skip single-quoted string
        if c == "'":
            i += 1
            while i < len(text) and text[i] != "'":
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip double-quoted string
        elif c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip template literal (backtick) — simplified, ignores ${...}
        elif c == '`':
            i += 1
            while i < len(text) and text[i] != '`':
                if text[i] == '\\':
                    i += 1
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth -= 1
        i += 1

    if depth == 0 and paren_depth == 0:
        return False  # already balanced

    # Prefer fixing paren imbalance first (simpler — just remove trailing `)`)
    if paren_depth < 0 and depth == 0:
        # Too many `)`: remove trailing `)` or `))` from the last line
        lines = text.rstrip().splitlines()
        new_lines = list(lines)
        removed = 0
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(paren_depth):
                break
            stripped = new_lines[idx].rstrip()
            if stripped.endswith(')') or stripped.endswith('))'):
                count = min(abs(paren_depth) - removed, stripped.count(')') - stripped.count('('))
                if count > 0:
                    new_lines[idx] = stripped[:-count]
                    removed += count
        if removed:
            Path(file_path).write_text('\n'.join(new_lines) + '\n')
            print(f"==> [mu-agent] Reflex: removed {removed} extra ')' from {file_path}")
            return True

    if depth < 0:
        # Too many `}`: remove or trim trailing `}` lines
        lines = text.rstrip().splitlines()
        removed = 0
        new_lines = list(lines)
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(depth):
                break
            stripped = new_lines[idx].strip()
            # Handle single `}` or `};` lines
            if stripped in ('}', '};'):
                del new_lines[idx]
                removed += 1
            # Handle `}}` or `}};` — remove one `}` at a time from the right
            elif re.match(r'^[}]+;?$', stripped) and len(stripped.rstrip(';')) > 1:
                extra = len(stripped.rstrip(';')) - 1
                to_remove = min(extra, abs(depth) - removed)
                new_stripped = stripped[to_remove:]
                new_lines[idx] = new_stripped
                removed += to_remove
        if not removed:
            return False
        Path(file_path).write_text('\n'.join(new_lines) + '\n')
        print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
        return True
    else:
        # Too many `{`: append `depth` closing braces
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True


def fix_csharp_missing_braces(file_path: str) -> bool:
    """Append missing closing braces to C# files with unbalanced brace counts.

    CS1513 '} expected' means the file has more `{` than `}`. This reflex counts
    braces (ignoring strings and comments) and appends the missing `}` characters.
    General: applies to any C# file, not specific to any program.
    """
    if not file_path.lower().endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Count braces outside strings and single-line comments
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Single-line comment — skip to end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if c == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    if depth == 0:
        return False
    if depth > 0:
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True
    # depth < 0: too many `}` — remove trailing standalone `}` lines
    lines = text.rstrip().splitlines()
    new_lines = list(lines)
    removed = 0
    for idx in range(len(lines) - 1, -1, -1):
        if removed >= abs(depth):
            break
        stripped = new_lines[idx].strip()
        if stripped == '}':
            del new_lines[idx]
            removed += 1
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(new_lines) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
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


_CODE_EXTS = {'.py', '.cs', '.rs', '.go', '.c', '.cpp', '.h', '.java', '.js', '.ts'}


def fix_tool_call_artifacts(file_path: str) -> bool:
    """Strip lines containing model tool-call JSON leaked into source files.

    Models occasionally embed their own tool-calling syntax (e.g. lines starting
    with backtick sequences followed by [TOOL_REQUEST]) directly into file content,
    producing immediate syntax errors. Generic: any such line in any source file
    is wrong.
    """
    if Path(file_path).suffix.lower() not in _CODE_EXTS:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    cleaned = [ln for ln in lines if '[TOOL_REQUEST]' not in ln and '[TOOL_RESULT]' not in ln]
    if len(cleaned) == len(lines):
        return False
    Path(file_path).write_text(''.join(cleaned))
    print(f"==> [mu-agent] Reflex: stripped tool-call artifact line(s) from {file_path}")
    return True


def fix_literal_newlines(file_path: str, lint_error: str = '') -> bool:
    """Replace literal \\n escape sequences with real newlines in source files.

    Models occasionally write an entire file as one long string with \\n
    characters instead of actual line breaks.

    Two modes:
    - Bulk mode: fires when literal \\n sequences outnumber real newlines by a
      wide margin (whole-file collapse). Safe to do a global replace on any
      source file.
    - Targeted mode (lint_error contains 'line continuation'): fires even in
      mixed files, but only replaces literal \\n outside string literals.
    """
    allowed_exts = _CODE_EXTS | {'.json'}
    if Path(file_path).suffix.lower() not in allowed_exts:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    real_newlines = text.count('\n')
    literal_newlines = text.count('\\n')
    if literal_newlines == 0:
        return False

    # Bulk mode: nearly all newlines are literal (whole-file collapse).
    if literal_newlines >= 3 and literal_newlines > real_newlines:
        fixed = text.replace('\\n', '\n')
        Path(file_path).write_text(fixed)
        print(f"==> [mu-agent] Reflex: replaced {literal_newlines} literal \\n "
              f"with real newlines in {file_path}")
        return True

    # JS/TS mode: even one literal \n outside a string is a syntax error.
    # JavaScript has no line-continuation character, so any \n in code is wrong.
    ext = Path(file_path).suffix.lower()
    is_js = ext in ('.js', '.jsx', '.ts', '.tsx')
    if is_js:
        lines = text.splitlines(keepends=True)
        changed = False
        result = []
        for line in lines:
            idx = line.find('\\n')
            if idx == -1:
                result.append(line)
                continue
            prefix = line[:idx]
            # Heuristic: if even number of unescaped quotes before \n, we're outside a string.
            if (prefix.count('"') - prefix.count('\\"')) % 2 == 0 and \
                    (prefix.count("'") - prefix.count("\\'")) % 2 == 0 and \
                    prefix.count('`') % 2 == 0:
                new_lines = line.replace('\\n', '\n')
                result.append(new_lines)
                changed = True
            else:
                result.append(line)
        if changed:
            Path(file_path).write_text(''.join(result))
            print(f"==> [mu-agent] Reflex: fixed literal \\n in JS/TS file {file_path}")
            return True

    # Targeted mode: mixed file with a 'line continuation' syntax error.
    # Replace \\n only on lines where it appears outside of a string literal
    # (heuristic: line contains \\n but is not dominated by quotes around it).
    if 'line continuation' not in lint_error:
        return False
    lines = text.splitlines(keepends=True)
    changed = False
    result = []
    for line in lines:
        # Count quotes before the first \\n to decide if we're inside a string.
        idx = line.find('\\n')
        if idx == -1:
            result.append(line)
            continue
        prefix = line[:idx]
        # If the number of unescaped quote chars before \\n is even, we're not
        # inside a string literal — safe to split.
        if (prefix.count('"') - prefix.count('\\"')) % 2 == 0 and \
                (prefix.count("'") - prefix.count("\\'")) % 2 == 0:
            # Replace all \\n in this line with real newlines by splitting.
            new_lines = line.replace('\\n', '\n')
            result.append(new_lines)
            changed = True
        else:
            result.append(line)
    if not changed:
        return False
    Path(file_path).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: fixed literal \\n (line continuation) in {file_path}")
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
    lines, in_recipe, orphans, clean = content.splitlines(), False, [], []
    for line in lines:
        trimmed = line.strip()
        if _TARGET_RE.match(line) and line and line[0] not in ('\t', ' '):
            in_recipe = True
            clean.append(line)
        elif line and line[0] == '\t':
            in_recipe = True
            clean.append(line)
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


_NESTED_TARGET_RE = re.compile(r'^\t([A-Za-z0-9_.-]+):([ \t].*)?$')


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

_GO_UNUSED_IMPORT_RE = re.compile(r'^(\S+):\d+:\d+: "([^"]+)" imported and not used')


def fix_go_unused_imports() -> bool:
    """Strip Go imports the compiler reports as unused.

    Go is strict: an `imported and not used` import is a hard compile error, and
    small models routinely emit speculative imports (`encoding/json`, `os`) they
    never reference. This uses the compiler as the oracle — problem-agnostic, no
    pattern-matching on specific packages — parsing `go build` errors of the form
    `./main.go:4:2: "encoding/json" imported and not used` and removing exactly
    the offending import line. Loops because removing one import can surface the
    next. Returns True if any import was removed.
    """
    if not shutil.which('go') or not any(Path('.').rglob('*.go')):
        return False
    removed_any = False
    for _ in range(8):
        proc = subprocess.run(['go', 'build', './...'],
                              capture_output=True, text=True, timeout=180)
        unused = {}  # file -> set of import paths
        for line in (proc.stderr or '').splitlines():
            m = _GO_UNUSED_IMPORT_RE.match(line.strip())
            if m:
                unused.setdefault(m.group(1), set()).add(m.group(2))
        if not unused:
            break
        progressed = False
        for fname, paths in unused.items():
            fp = Path(fname)
            if not fp.exists():
                continue
            kept = []
            for ln in fp.read_text().splitlines():
                stripped = ln.strip()
                # import line is `"path"` or `alias "path"` inside an import block
                if any(stripped == f'"{p}"' or stripped.endswith(f' "{p}"')
                       for p in paths):
                    progressed = removed_any = True
                    continue
                kept.append(ln)
            fp.write_text('\n'.join(kept) + '\n')
        if not progressed:
            break
    return removed_any


_UNDEF_RE = re.compile(r'(?:vet: )?\./([\w/.-]+\.go):\d+:\d+: undefined: (\w+)')

# stdlib packages whose package name doesn't equal the last path segment, or
# that models commonly omit. Keyed by the identifier used in source.
_STDLIB_IMPORTS: dict[str, str] = {
    'httptest':  'net/http/httptest',
    'http':      'net/http',
    'url':       'net/url',
    'json':      'encoding/json',
    'rand':      'math/rand',
    'filepath':  'path/filepath',
    'ioutil':    'io/ioutil',
    'bufio':     'bufio',
    'context':   'context',
    'errors':    'errors',
    'fmt':       'fmt',
    'io':        'io',
    'log':       'log',
    'math':      'math',
    'os':        'os',
    'sort':      'sort',
    'strconv':   'strconv',
    'strings':   'strings',
    'sync':      'sync',
    'time':      'time',
}


def fix_go_missing_pkg_imports() -> bool:
    """Add imports to Go files for identifiers that are undefined but resolvable.

    Covers two sources: packages in go.mod (third-party) and a table of
    commonly omitted stdlib packages (e.g. httptest → net/http/httptest).

    When ``go build`` reports ``undefined: X`` and go.mod requires a module
    whose last path component is X, the import was simply omitted from that
    file (common in test files that use a framework package like gin without
    importing it explicitly). This reflex adds the missing import line.

    Uses the compiler as oracle — problem-agnostic: it reads go.mod, not a
    hardcoded list of packages.
    """
    if not shutil.which('go') or not Path('go.mod').exists():
        return False
    proc = subprocess.run(['go', 'vet', './...'], capture_output=True,
                          text=True, timeout=60)
    stderr = proc.stderr or ''
    file_ids: dict[str, set[str]] = {}
    for line in stderr.splitlines():
        m = _UNDEF_RE.search(line)
        if m:
            file_ids.setdefault(m.group(1), set()).add(m.group(2))
    if not file_ids:
        return False

    # Build map: last-path-component → full import path (from go.mod require lines).
    # Handles both `require M v` (single) and block form `\tM v` (indented).
    gomod = Path('go.mod').read_text()
    req_re = re.compile(r'(?:^require\s+|^\s+)([\w./\-]+)\s+v', re.MULTILINE)
    pkg_map = {m.group(1).split('/')[-1]: m.group(1) for m in req_re.finditer(gomod)}

    changed = False
    for fname, idents in file_ids.items():
        fp = Path(fname)
        if not fp.exists():
            continue
        src = fp.read_text()
        to_add = []
        for i in idents:
            imp = pkg_map.get(i) or _STDLIB_IMPORTS.get(i)
            if imp and f'"{imp}"' not in src:
                to_add.append(imp)
        if not to_add:
            continue
        lines = src.splitlines()
        for idx, line in enumerate(lines):
            if line.strip() == 'import (':
                for imp in to_add:
                    lines.insert(idx + 1, f'\t"{imp}"')
                fp.write_text('\n'.join(lines) + '\n')
                changed = True
                break
        else:
            # No import block — insert one after the package line
            for idx, line in enumerate(lines):
                if line.startswith('package '):
                    block = ['', 'import ('] + [f'\t"{i}"' for i in to_add] + [')']
                    lines[idx + 1:idx + 1] = block
                    fp.write_text('\n'.join(lines) + '\n')
                    changed = True
                    break
    return changed


def apply_go_reflexes() -> bool:
    """Resolve Go module dependencies and clean unused imports before a build.

    Generic, problem-agnostic toolchain steps: any Go project with source files
    needs a module file (`go mod init`) and its declared imports fetched
    (`go mod tidy`) — the package manager is the authority on dependency names
    and versions, not the model's guess — and Go's compiler rejects unused
    imports outright, so we let the compiler name them and strip them. Idempotent
    and safe to call repeatedly. Returns True if the go toolchain ran.
    """
    if not shutil.which('go') or not any(Path('.').rglob('*.go')):
        return False
    if not Path('go.mod').exists():
        module = Path.cwd().name or 'app'
        subprocess.run(['go', 'mod', 'init', module], capture_output=True, text=True)
    # tidy adds missing requires (e.g. gin) and writes go.sum; needs network.
    subprocess.run(['go', 'mod', 'tidy'], capture_output=True, text=True, timeout=180)
    fix_go_unused_imports()
    fix_go_missing_pkg_imports()
    return True


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


def fix_jest_no_tests_found(test_output: str, project_dir: str) -> bool:
    """Add testRegex to package.json when Jest reports 'No tests found'.

    Jest's default testMatch pattern requires `.test.js` / `.spec.js` suffixes.
    When a project uses `_test.js` (Python-style) or another convention, Jest
    exits 1 with 'No tests found'. This reflex broadens the testRegex in
    package.json to match `_test.js` / `_spec.js` in addition to the defaults.
    General: driven entirely by Jest's error message, not any specific project.
    """
    if 'No tests found' not in test_output:
        return False
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    if 'jest' not in all_deps:
        return False
    # Already has testRegex or testMatch configured — don't override.
    jest_cfg = data.get('jest', {})
    if jest_cfg.get('testRegex') or jest_cfg.get('testMatch'):
        return False
    # Find actual test files in the project dir to figure out their naming.
    existing = [
        p.name for p in Path(project_dir).iterdir()
        if p.is_file() and re.search(r'[._](test|spec)\.[jt]sx?$', p.name)
    ]
    if not existing:
        return False
    # Match both dot-separated (.test.js, .spec.js) and underscore-separated
    # (_test.js, _spec.js) conventions. `[._]` covers both separators.
    data.setdefault('jest', {})['testRegex'] = r'.*[._](test|spec)\.[jt]sx?$'
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: added Jest testRegex to {pkg_path} (No tests found)")
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
    missing_binaries = [p for p in prereqs
                        if p not in declared and '.' not in p and not p.startswith('.')]
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
                if words and all(w in declared for w in words) and words != [target]:
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
    # Match tab-indented recipe lines containing bare `vitest` (not `npx vitest`)
    new_content = re.sub(
        r'(?m)^(\t[^\n]*)\bvitest\b(?!\s+run\b)(?!\s*:)',
        lambda m: re.sub(r'\bvitest\b(?!\s+run\b)', 'npx vitest run', m.group(0)),
        content,
    )
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced bare vitest with npx vitest run in {f}")
    return True


def apply_makefile_reflexes(f: str) -> None:
    for fn in [fix_makefile_literal_tab_escape, fix_makefile_literal_newline_escape,
               fix_makefile_escaped_dollar,
               fix_makefile_wrong_c_compiler,
               fix_makefile_sdl2_config_typo, fix_makefile_double_colon_target,
               fix_makefile_space_indent, fix_nested_targets,
               fix_orphan_top_level_commands, fix_no_targets,
               fix_inline_recipe, fix_binary_target_runs_itself,
               fix_makefile_missing_compile_rule,
               fix_makefile_recipe_is_prerequisite_list,
               fix_duplicate_var, fix_python_venv_cmd, fix_makefile_pip_no_venv,
               fix_makefile_bare_pytest, fix_makefile_npm_test_jest,
               fix_makefile_bare_vitest,
               fix_missing_venv_rule,
               fix_config_tool_redundant_flag]:
        fn(f)
