"""Rust / Cargo reflexes: deterministic post-write fixers for Rust sources and

One fixer per file (see AGENTS.md §3a); this package re-exports them.
"""

from .fix_rust_println_missing_arg import fix_rust_println_missing_arg
from .fix_rust_cargo_toml import fix_rust_cargo_toml
from .fix_rust_cargo_bad_dependency import fix_rust_cargo_bad_dependency
from .fix_rust_duplicate_use import fix_rust_duplicate_use
from .fix_rust_unbalanced_braces import fix_rust_unbalanced_braces
from .fix_rust_missing_trait_import import fix_rust_missing_trait_import
from .apply_rust_source_reflexes import apply_rust_source_reflexes

__all__ = [
    'fix_rust_println_missing_arg',
    'fix_rust_cargo_toml',
    'fix_rust_cargo_bad_dependency',
    'fix_rust_duplicate_use',
    'fix_rust_unbalanced_braces',
    'fix_rust_missing_trait_import',
    'apply_rust_source_reflexes',
]
