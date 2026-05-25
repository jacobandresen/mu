"""Deterministic code fixers applied after model writes."""

import re
import ast
import shutil
import subprocess
from pathlib import Path

_TARGET_RE = re.compile(r'(?m)^[a-zA-Z_.][a-zA-Z0-9._-]*\s*:')
_KNOWN_TARGETS = {'all', 'clean', 'install', 'test', 'build', 'run', 'format',
                  'lint', 'check', 'release', 'debug', 'help'}


# ── Python sensors ────────────────────────────────────────────────────────────

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


def ruff_autofix(file_path: str) -> bool:
    """Run ruff --fix on a Python file. Returns True if ruff ran."""
    if not shutil.which('ruff') or not file_path.lower().endswith('.py'):
        return False
    subprocess.run(['ruff', 'check', '--fix', '--select=E9,F', file_path],
                   capture_output=True)
    return True


# ── Makefile sensors ──────────────────────────────────────────────────────────

# ── AST‑based generic fixers ──────────────────────────────────────────────────────

def _run_ast_fixers(file_path: str) -> bool:
    """Dispatch language‑specific AST fixers. Return True if any fixer touched the file.

    Supported extensions: .py, .rs, .go (via a simple brace‑count approach).
    The function is deterministic and language‑agnostic – it never adds code that
    is specific to a particular problem, only generic scaffolding such as missing
    imports or stray top‑level statements.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == '.py':
        return _fix_python_ast(file_path)
    if suffix == '.rs':
        return _fix_rust_ast(file_path)
    if suffix == '.go':
        return _fix_go_ast(file_path)
    return False

def _fix_python_ast(fp: str) -> bool:
    """Add missing imports for undefined names in a Python module.

    The algorithm:
    1. Parse the file with ``ast`` and collect all names that are loaded (used)
       but not defined/imported in the module.
    2. For each missing name, try to import it from a sibling module of the same
       name (case‑insensitive). If no sibling matches, fall back to a plain
       ``import <name>``.
    3. Prepend the generated import lines after any shebang/encoding comment.
    Returns ``True`` if the file was modified.
    """
    try:
        src = Path(fp).read_text()
        tree = ast.parse(src, filename=fp)
    except (SyntaxError, OSError):
        return False

    used: set[str] = set()
    defined: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:  # type: ignore[override]
            if isinstance(node.ctx, ast.Load):
                used.add(node.id)
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
            defined.add(node.name)
            self.generic_visit(node)
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # type: ignore[override]
            defined.add(node.name)
            self.generic_visit(node)
        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
            defined.add(node.name)
            self.generic_visit(node)
        def visit_Import(self, node: ast.Import) -> None:  # type: ignore[override]
            for alias in node.names:
                defined.add(alias.asname or alias.name.split('.')[0])
        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # type: ignore[override]
            for alias in node.names:
                defined.add(alias.asname or alias.name)

    Visitor().visit(tree)
    missing = used - defined
    if not missing:
        return False

    sibling_modules = {p.stem.lower() for p in Path(fp).parent.glob('*.py') if p.name != Path(fp).name}
    imports_added: list[str] = []
    for name in sorted(missing):
        lname = name.lower()
        if lname in sibling_modules:
            imports_added.append(f"from {lname} import {name}")
        else:
            imports_added.append(f"import {name}")

    if not imports_added:
        return False

    lines = src.splitlines()
    insert_at = 0
    if lines and (lines[0].startswith('#!') or lines[0].startswith('# -*-')):
        insert_at = 1
    existing = set(lines)
    filtered = [imp for imp in imports_added if imp not in existing]
    if not filtered:
        return False
    new_src = '\n'.join(lines[:insert_at] + filtered + lines[insert_at:]) + '\n'
    Path(fp).write_text(new_src)
    return True

def _fix_rust_ast(fp: str) -> bool:
    """Remove any top‑level statements that appear after the outermost function.

    Rust allows only items at the crate level. A stray statement after the closing
    brace of the last function causes a syntax error. This fixer counts braces and
    discards any lines once the brace depth drops below zero.
    Returns ``True`` if the file was rewritten.
    """
    try:
        src = Path(fp).read_text()
    except OSError:
        return False
    brace = 0
    keep: list[str] = []
    changed = False
    for line in src.splitlines():
        stripped = line.strip()
        brace += stripped.count('{')
        brace -= stripped.count('}')
        if brace < 0:
            changed = True
            continue
        keep.append(line)
    if not changed:
        return False
    Path(fp).write_text('\n'.join(keep) + '\n')
    return True

def _fix_go_ast(fp: str) -> bool:
    """Thin wrapper that re‑uses the existing Go unused‑import sensor.

    The generic Go sensor already removes unused imports; we expose it here so
    the AST dispatcher can treat ``.go`` files uniformly.
    """
    # Re‑use the existing function; it returns True if any import was removed.
    return fix_go_unused_imports()


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


def apply_go_sensors() -> bool:
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


def apply_makefile_sensors(f: str) -> None:
    for fn in [fix_makefile_space_indent, fix_orphan_top_level_commands,
               fix_no_targets, fix_inline_recipe, fix_duplicate_var]:
        fn(f)
