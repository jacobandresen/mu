import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

from .fix_js_dot_bracket_access import fix_js_dot_bracket_access
from .fix_js_duplicate_const import fix_js_duplicate_const
from .fix_js_duplicate_require import fix_js_duplicate_require
from .fix_js_env_data_file import fix_js_env_data_file
from .fix_js_missing_requires import fix_js_missing_requires
from .fix_js_same_scope_redeclaration import fix_js_same_scope_redeclaration

def apply_js_repair_reflexes(file_path: str, test_output: str = '') -> None:
    """Repair-phase JS/TS chain — preserves the order used in agent.py ~1341."""
    if Path(file_path).suffix.lower() not in _JS_EXTS:
        return
    noted(fix_js_duplicate_require, file_path)
    noted(fix_js_duplicate_const, file_path, test_output)
    noted(fix_js_same_scope_redeclaration, file_path, test_output)
    noted(fix_js_dot_bracket_access, file_path, test_output)
    noted(fix_js_env_data_file, file_path)
    noted(fix_js_missing_requires, file_path)
    noted(fix_literal_newlines, file_path)
