"""Makefile / build-system reflexes: deterministic post-write fixers for
Makefiles — tab/indent repair, target/recipe structure, venv & pip rules, and
the makefile-level test-command fixers (pytest/jest/vitest). Split out of the
monolithic reflexes module so each language's fixers live together. No logic
changes from the original.
"""

import re
import shutil
from pathlib import Path

from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts


__all__ = [
    'fix_makefile_space_indent',
    'fix_orphan_top_level_commands',
    'fix_no_targets',
    'fix_inline_recipe',
    'fix_makefile_backslash_artifact',
    'fix_nested_targets',
    'fix_binary_target_runs_itself',
    'fix_duplicate_var',
    'fix_python_venv_cmd',
    'fix_makefile_npm_test_jest',
    'fix_makefile_escaped_dollar',
    'fix_makefile_pytest_in_non_python',
    'fix_makefile_bare_pytest',
    'fix_makefile_pip_no_venv',
    'fix_makefile_pip_install_empty',
    'fix_missing_venv_rule',
    'fix_makefile_literal_tab_escape',
    'fix_makefile_literal_newline_escape',
    'fix_makefile_binary_name',
    'fix_makefile_wrong_c_compiler',
    'fix_makefile_double_colon_target',
    'fix_makefile_missing_compile_rule',
    'fix_makefile_sdl2_config_typo',
    'fix_config_tool_redundant_flag',
    'fix_makefile_recipe_is_prerequisite_list',
    'fix_makefile_bare_vitest',
    'apply_makefile_reflexes',
]


_TARGET_RE = re.compile(r'(?m)^(?:\$[({][A-Za-z_]\w*[)}]|[a-zA-Z_.][a-zA-Z0-9._-]*)\s*:')

_KNOWN_TARGETS = {'all', 'clean', 'install', 'test', 'build', 'run', 'format',
                  'lint', 'check', 'release', 'debug', 'help'}

_INLINE_COMPILER_RE = re.compile(
    r'^(?:cc|clang|gcc|g\+\+|clang\+\+|go|cargo|dotnet|python3?|rustc|make)\b'
)

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
    """Run the whole Makefile reflex chain over a file to a fixpoint."""
    run_reflexes(_MAKEFILE_REFLEXES, f)
