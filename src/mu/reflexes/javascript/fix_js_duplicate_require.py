import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_duplicate_require(file_path: str) -> bool:
    """Remove a duplicate top-level ``const X = require(...)`` declaration.

    A weak model sometimes emits the same require twice (observed:
    ``const fs = require('fs')`` on two lines), which is a hard
    ``SyntaxError: Identifier 'fs' has already been declared`` — Jest/Babel can't
    even parse the file. Keep the first declaration of each name and drop later
    ones. General: re-declaring the same identifier with ``const`` is always
    invalid JS, in any file — the JS analogue of fix_rust_duplicate_use.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    def _match(line: str):
        m = _JS_REQUIRE_DECL_RE.match(line)
        return m.group('name') if m else None
    removed = _fix_duplicate_decls(file_path, _match, keepends=False)
    if removed:
        print(f"==> [mu-agent] Reflex: removed {removed} duplicate require declaration(s) from {file_path}")
    return removed > 0
