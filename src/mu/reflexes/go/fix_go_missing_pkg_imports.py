import re
import shutil
import subprocess
from pathlib import Path

from ._common import *  # noqa: F401,F403

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
