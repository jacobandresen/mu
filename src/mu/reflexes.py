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

import re
import shutil
import subprocess
from pathlib import Path

_TARGET_RE = re.compile(r'(?m)^[a-zA-Z_.][a-zA-Z0-9._-]*\s*:')
_KNOWN_TARGETS = {'all', 'clean', 'install', 'test', 'build', 'run', 'format',
                  'lint', 'check', 'release', 'debug', 'help'}


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


# ── Makefile reflexes ─────────────────────────────────────────────────────────

def fix_makefile_space_indent(f: str) -> bool:
    """Convert space-indented recipe lines to tab-indented."""
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
                if target in _KNOWN_TARGETS and ' ' in after and not after.startswith('='):
                    out.extend([target + ':', '\t' + after])
                    changed = True
                    continue
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True


_NESTED_TARGET_RE = re.compile(r'^\t([A-Za-z0-9_.-]+):[ \t]*$')


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
            recipe: list[str] = [name + ':']
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

    for block in extracted:
        out.append('')
        out.extend(block)

    Path(f).write_text('\n'.join(out))
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


def apply_makefile_reflexes(f: str) -> None:
    for fn in [fix_makefile_space_indent, fix_nested_targets,
               fix_orphan_top_level_commands, fix_no_targets,
               fix_inline_recipe, fix_binary_target_runs_itself,
               fix_duplicate_var, fix_python_venv_cmd]:
        fn(f)
