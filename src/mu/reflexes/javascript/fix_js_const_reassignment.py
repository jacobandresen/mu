import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_const_reassignment(file_path: str, test_output: str) -> bool:
    """Change `const` to `let` for variables that are reassigned after declaration.

    When test output contains 'Assignment to constant variable', the model
    declared a variable with `const` but later reassigns it. Scans for each
    `const NAME` declaration and checks if NAME appears in a bare assignment
    (= not ==) later in the same file.
    """
    if 'Assignment to constant variable' not in test_output:
        return False
    if Path(file_path).suffix.lower() not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    changed = False

    def check_reassign(m: re.Match) -> str:
        nonlocal changed
        name = m.group(1)
        after = text[m.end():]
        # bare assignment: NAME = ... but not ==, ===, !=, +=, -=, etc.
        if re.search(
            rf'(?<![=!<>+\-*/%&|^])\b{re.escape(name)}\s*=(?![=>])',
            after,
        ):
            changed = True
            return f'let {name}'
        return m.group(0)

    new_text = re.sub(r'\bconst\s+(\w+)', check_reassign, text)
    if not changed:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: changed const→let for reassigned variable(s) in {file_path}")
    return True
