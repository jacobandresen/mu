"""JavaScript / Node / Jest / Vitest / Vue reflexes: deterministic post-write

One fixer per file (see AGENTS.md §3a); this package re-exports them.
"""

from .fix_vue_missing_package import fix_vue_missing_package
from .fix_vitest_watch_mode import fix_vitest_watch_mode
from .fix_vitest_globals import fix_vitest_globals
from .fix_js_env_data_file import fix_js_env_data_file
from .fix_js_missing_requires import fix_js_missing_requires
from .fix_js_duplicate_require import fix_js_duplicate_require
from .fix_js_extra_closing_brace import fix_js_extra_closing_brace
from .fix_jest_fs_mock import fix_jest_fs_mock
from .fix_vue_test_utils_import import fix_vue_test_utils_import
from .fix_jest_no_tests_found import fix_jest_no_tests_found
from .fix_jest_esm import fix_jest_esm
from .fix_jest_config_js import fix_jest_config_js
from .fix_package_json_bare_jest import fix_package_json_bare_jest
from .fix_package_json_builtin_deps import fix_package_json_builtin_deps
from .fix_js_const_reassignment import fix_js_const_reassignment
from .fix_js_duplicate_const import fix_js_duplicate_const
from .fix_js_same_scope_redeclaration import fix_js_same_scope_redeclaration
from .fix_js_dot_bracket_access import fix_js_dot_bracket_access
from .fix_js_program_parse_guard import fix_js_program_parse_guard
from .fix_vue_attr_quotes import fix_vue_attr_quotes
from .fix_js_parent_to_sibling_import import fix_js_parent_to_sibling_import
from .apply_js_write_reflexes import apply_js_write_reflexes
from .apply_js_repair_reflexes import apply_js_repair_reflexes

__all__ = [
    'fix_vue_missing_package',
    'fix_vitest_watch_mode',
    'fix_vitest_globals',
    'fix_js_env_data_file',
    'fix_js_missing_requires',
    'fix_js_extra_closing_brace',
    'fix_jest_fs_mock',
    'fix_vue_test_utils_import',
    'fix_jest_no_tests_found',
    'fix_jest_esm',
    'fix_jest_config_js',
    'fix_package_json_bare_jest',
    'fix_package_json_builtin_deps',
    'fix_js_duplicate_require',
    'fix_js_const_reassignment',
    'fix_js_duplicate_const',
    'fix_js_same_scope_redeclaration',
    'fix_js_dot_bracket_access',
    'fix_vue_attr_quotes',
    'fix_js_parent_to_sibling_import',
    'apply_js_write_reflexes',
    'apply_js_repair_reflexes',
]
