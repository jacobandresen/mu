"""Python reflexes: deterministic post-write fixers for Python sources — syntax

One fixer per file (see AGENTS.md §3a); this package re-exports them.
"""

from .fix_multiline_single_quote import fix_multiline_single_quote
from .fix_missing_close_paren import fix_missing_close_paren
from .fix_test_import_module import fix_test_import_module
from .py_autofix import py_autofix
from .fix_python_missing_project_imports import fix_python_missing_project_imports
from .fix_python_undefined_imports import fix_python_undefined_imports
from .fix_sqlite_test_isolation import fix_sqlite_test_isolation
from .fix_sqlite_memory_multi_connect import fix_sqlite_memory_multi_connect
from .fix_sqlite_path_unlink import fix_sqlite_path_unlink
from .fix_python_missing_stdlib_imports import fix_python_missing_stdlib_imports
from .fix_requirements_stdlib_entries import fix_requirements_stdlib_entries
from .fix_missing_pip_packages import fix_missing_pip_packages
from .fix_python_unindented_body import fix_python_unindented_body
from .fix_python_method_indent import fix_python_method_indent
from .fix_python_decorator_colon import fix_python_decorator_colon
from .fix_python_missing_def import fix_python_missing_def
from .fix_sqlite_conn_scope import fix_sqlite_conn_scope
from .fix_sqlite_missing_row_factory import fix_sqlite_missing_row_factory
from .fix_sqlite_class_missing_init_table import fix_sqlite_class_missing_init_table
from .fix_flask_post_missing_201 import fix_flask_post_missing_201
from .fix_flask_test_route_decorators import fix_flask_test_route_decorators
from .fix_flask_init_db_import import fix_flask_init_db_import
from .fix_missing_flask_client_fixture import fix_missing_flask_client_fixture
from .fix_requirements_path_entries import fix_requirements_path_entries

__all__ = [
    'fix_multiline_single_quote',
    'fix_missing_close_paren',
    'fix_test_import_module',
    'py_autofix',
    'fix_python_missing_project_imports',
    'fix_python_undefined_imports',
    'fix_sqlite_test_isolation',
    'fix_sqlite_memory_multi_connect',
    'fix_sqlite_path_unlink',
    'fix_python_missing_stdlib_imports',
    'fix_requirements_stdlib_entries',
    'fix_missing_pip_packages',
    'fix_python_method_indent',
    'fix_python_unindented_body',
    'fix_python_decorator_colon',
    'fix_python_missing_def',
    'fix_sqlite_missing_row_factory',
    'fix_sqlite_conn_scope',
    'fix_sqlite_class_missing_init_table',
    'fix_flask_post_missing_201',
    'fix_flask_test_route_decorators',
    'fix_flask_init_db_import',
    'fix_missing_flask_client_fixture',
    'fix_requirements_path_entries',
]
