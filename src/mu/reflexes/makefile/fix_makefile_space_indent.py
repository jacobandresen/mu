import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_space_indent(f: str) -> bool:
    """Fix recipe lines that are not tab-indented.

    Covers two cases:
    - Space-indented recipes (leading spaces → TAB).
    - Flush-left recipes (no leading whitespace after a target line → TAB added).
    Both produce "missing separator" from make.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if not _TARGET_RE.search(content):
        return False
    lines, changed, in_recipe, out = content.splitlines(), False, False, []
    for line in lines:
        trimmed = line.strip()
        if _TARGET_RE.match(line) and line and line[0] not in ('\t', ' '):
            in_recipe = True
            out.append(line)
        elif line and line[0] == '\t':
            in_recipe = True
            out.append(line)
        elif not trimmed:
            in_recipe = False
            out.append(line)
        elif in_recipe and line and line[0] == ' ':
            out.append('\t' + line.lstrip(' '))
            changed = True
        elif in_recipe and line and line[0] not in ('\t', '#') and not _TARGET_RE.match(line):
            # Flush-left command after a target — missing tab entirely.
            out.append('\t' + line)
            changed = True
        else:
            in_recipe = False
            out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True
