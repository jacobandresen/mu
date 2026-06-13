import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_duplicate_const(file_path: str, test_output: str = '') -> bool:
    """Remove exact-duplicate consecutive const/let declarations in test files.

    Jest reports "Identifier 'X' has already been declared" when a const is
    declared twice. Common LLM pattern: the same `const X = ...` line appears
    consecutively (identical or with only whitespace differences). Removing the
    duplicate line fixes the syntax error without breaking surrounding code.
    Only fires on test files and only for consecutive exact duplicates.
    """
    if test_output and 'has already been declared' not in test_output:
        return False
    if Path(file_path).suffix.lower() not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    basename = Path(file_path).name
    if not (basename.startswith('test') or 'test' in basename or 'spec' in basename):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    lines = text.splitlines(keepends=True)
    stripped = [l.strip() for l in lines]
    new_lines = []
    i = 0
    changed = False
    while i < len(lines):
        # Check if this line is a const/let/var declaration that matches next line
        if (i + 1 < len(lines) and
                re.match(r'(?:const|let|var)\s+\w+\s*=', stripped[i]) and
                stripped[i] == stripped[i + 1]):
            # Skip the duplicate (keep first, drop second)
            new_lines.append(lines[i])
            i += 2
            changed = True
        else:
            new_lines.append(lines[i])
            i += 1

    if not changed:
        return False
    Path(file_path).write_text(''.join(new_lines))
    print(f"==> [mu-agent] Reflex: removed duplicate const declaration in {file_path}")
    return True
