"""Shared helpers and constants for the rust reflexes."""

import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls


_CARGO_DEP_SECTIONS = ('[dependencies]', '[dev-dependencies]', '[build-dependencies]')


_CARGO_DEP_LINE = re.compile(r'^\s*([A-Za-z0-9_-]+)\s*=\s*["\']([^"\']*)["\']\s*$')


__all__ = ['_CARGO_DEP_SECTIONS', '_CARGO_DEP_LINE']
