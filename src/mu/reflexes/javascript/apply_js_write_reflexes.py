import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

from .fix_jest_fs_mock import fix_jest_fs_mock
from .fix_js_duplicate_require import fix_js_duplicate_require
from .fix_js_env_data_file import fix_js_env_data_file
from .fix_js_missing_requires import fix_js_missing_requires
from .fix_js_parent_to_sibling_import import fix_js_parent_to_sibling_import
from .fix_js_program_parse_guard import fix_js_program_parse_guard
from .fix_vue_attr_quotes import fix_vue_attr_quotes
from .fix_vue_test_utils_import import fix_vue_test_utils_import

def apply_js_write_reflexes(file_path: str) -> None:
    """Write-phase JS/TS/Vue chain — preserves the order used in agent.py ~795-811."""
    ext = Path(file_path).suffix.lower()
    if ext not in _JS_EXTS and not file_path.lower().endswith('.vue'):
        return
    noted(fix_jest_fs_mock, file_path)
    noted(fix_vue_test_utils_import, file_path)
    noted(fix_vue_attr_quotes, file_path)
    noted(fix_js_duplicate_require, file_path)
    noted(fix_js_env_data_file, file_path)
    noted(fix_js_missing_requires, file_path)
    noted(fix_js_parent_to_sibling_import, file_path)
    noted(fix_js_program_parse_guard, file_path)
