import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_duplicate_use(file_path: str) -> bool:
    """Remove exact duplicate `use` lines from a Rust source file.

    The model sometimes emits the same `use std::io::{self, Write};` line twice,
    causing E0252 'name defined multiple times'. Dedup in order of first occurrence.
    """
    if not file_path.endswith('.rs'):
        return False
    def _match(line: str):
        s = line.strip()
        return s if s.startswith('use ') else None
    removed = _fix_duplicate_decls(file_path, _match, keepends=True)
    if removed:
        print(f"==> [mu-agent] Reflex: removed duplicate use statement(s) in {file_path}")
    return removed > 0
