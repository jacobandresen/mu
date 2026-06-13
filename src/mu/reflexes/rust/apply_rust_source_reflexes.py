import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

from .fix_rust_duplicate_use import fix_rust_duplicate_use
from .fix_rust_println_missing_arg import fix_rust_println_missing_arg

def apply_rust_source_reflexes(file_path: str) -> None:
    """Write-phase .rs chain — preserves the order used in agent.py ~823."""
    if not file_path.endswith('.rs'):
        return
    fix_rust_duplicate_use(file_path)
    fix_rust_println_missing_arg(file_path)
