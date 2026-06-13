import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_missing_trait_import(file_path: str, build_output: str) -> bool:
    """Add missing trait `use` statements when rustc says 'the trait is in scope'.

    rustc E0599 often says:
      "trait `Write` which provides `flush` is implemented but not in scope;
       perhaps you want to import it: `use std::io::Write;`"
    This reflex extracts the suggested `use` statement and adds it to the file.
    General: driven entirely by the compiler's suggestion, not any specific program.
    """
    if not file_path.endswith('.rs'):
        return False
    if not any(c in build_output for c in ('E0599', 'E0425', 'not in scope', 'not found in this scope')):
        return False
    # Parse suggested `use X::Y;` lines: both inline backtick format and diff-style "N + use ..."
    suggestions = re.findall(r'`(use [^`]+;)`', build_output)
    suggestions += re.findall(r'^\s*\d+\s*\+\s*(use [^;]+;)', build_output, re.MULTILINE)
    if not suggestions:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    to_add = [stmt for stmt in suggestions if stmt not in text]
    if not to_add:
        return False
    lines = text.splitlines()
    # Insert after the last existing use statement
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('use '):
            insert_at = i + 1
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added missing trait import(s) to {file_path}: {to_add}")
    return True
