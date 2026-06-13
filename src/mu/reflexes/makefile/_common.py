"""Shared helpers and constants for the makefile reflexes."""

import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts


_TARGET_RE = re.compile(r'(?m)^(?:\$[({][A-Za-z_]\w*[)}]|[a-zA-Z_.][a-zA-Z0-9._-]*)\s*:')


_KNOWN_TARGETS = {'all', 'clean', 'install', 'test', 'build', 'run', 'format',
                  'lint', 'check', 'release', 'debug', 'help'}


_INLINE_COMPILER_RE = re.compile(
    r'^(?:cc|clang|gcc|g\+\+|clang\+\+|go|cargo|dotnet|python3?|rustc|make)\b'
)


_NESTED_TARGET_RE = re.compile(r'^\t(\$[({][A-Za-z_]\w*[)}]|[A-Za-z0-9_.-]+):([ \t].*)?$')


_COMPILE_IN_RECIPE_RE = re.compile(
    r'^\t.*\b(gcc|clang|cc|g\+\+|clang\+\+)\b.*\s-o\s+(\S+)', re.MULTILINE
)


__all__ = ['_TARGET_RE', '_KNOWN_TARGETS', '_INLINE_COMPILER_RE', '_NESTED_TARGET_RE', '_COMPILE_IN_RECIPE_RE']
