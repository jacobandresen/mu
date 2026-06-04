"""Go reflexes: deterministic post-write fixers for Go sources — driving
``go mod tidy``/``go vet`` and patching unused/missing imports. Split out of the
monolithic reflexes module so each language's fixers live together. No logic
changes from the original.
"""

import re
import shutil
import subprocess
from pathlib import Path


__all__ = [
    'fix_go_unused_imports',
    'fix_go_missing_pkg_imports',
    'apply_go_reflexes',
]


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
