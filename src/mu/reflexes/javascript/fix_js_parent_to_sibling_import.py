import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_parent_to_sibling_import(file_path: str) -> bool:
    """Replace '../Foo.vue' import with './Foo.vue' when the sibling exists but parent doesn't.

    LLMs place test files in src/ but import the component as '../App.vue' (one
    level up) instead of './App.vue' (same directory). Vite fails with 'Failed to
    resolve import'. Only fires when the parent path doesn't exist AND the sibling
    path does, so it's safe to apply unconditionally.
    General: any .ts/.js test file in the project with this wrong relative import.
    """
    if Path(file_path).suffix.lower() not in ('.ts', '.tsx', '.js', '.jsx', '.mjs'):
        return False
    try:
        content = Path(file_path).read_text()
    except OSError:
        return False

    file_dir = Path(file_path).parent
    changed = False

    def _fix(m: re.Match) -> str:
        nonlocal changed
        imp = m.group(1)
        if not imp.startswith('../'):
            return m.group(0)
        name = imp[3:]  # strip leading '../'
        if (file_dir / name).exists() and not (file_dir.parent / name).exists():
            changed = True
            return m.group(0).replace('../' + name, './' + name, 1)
        return m.group(0)

    new_content = re.sub(
        r"""(?:from|import\s+\w+\s+from)\s+['"](\.\./[^'"]+)['"]""",
        _fix,
        content,
    )
    if not changed:
        return False
    Path(file_path).write_text(new_content)
    print(f"==> [mu-agent] Reflex: fixed parent-level import path in {file_path}")
    return True
