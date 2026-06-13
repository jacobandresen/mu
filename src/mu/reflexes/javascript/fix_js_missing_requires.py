import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

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
