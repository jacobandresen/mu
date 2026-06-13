import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_method_indent(file_path: str) -> bool:
    """Fix a `def` that lost its indentation after a class-level decorator.

    When a model writes `    @staticmethod\\ndef foo():` (decorator indented,
    def at column 0), Python raises IndentationError. This reflex re-indents
    the def line to match the decorator immediately above it.
    General: applies whenever an indented @decorator is followed by an unindented def.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    result = []
    changed = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if (i > 0 and stripped.startswith('def ') and not line[0].isspace()):
            prev = result[-1] if result else ''
            prev_stripped = prev.lstrip()
            if prev_stripped.startswith('@'):
                # Re-indent the def to match the decorator
                indent = prev[:len(prev) - len(prev_stripped)]
                result.append(indent + stripped)
                changed = True
                continue
        result.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: fixed method indentation after decorator in {file_path}")
    return True
