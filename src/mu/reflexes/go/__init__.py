"""Go reflexes: deterministic post-write fixers for Go sources — driving

One fixer per file (see AGENTS.md §3a); this package re-exports them.
"""

from .fix_go_unused_imports import fix_go_unused_imports
from .fix_go_missing_pkg_imports import fix_go_missing_pkg_imports
from .fix_go_trailing_dot import fix_go_trailing_dot
from .apply_go_reflexes import apply_go_reflexes

__all__ = [
    'fix_go_unused_imports',
    'fix_go_missing_pkg_imports',
    'fix_go_trailing_dot',
    'apply_go_reflexes',
]
