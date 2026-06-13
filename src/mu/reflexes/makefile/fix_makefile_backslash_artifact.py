import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_backslash_artifact(f: str) -> bool:
    """Strip a stray backslash a model puts before inline whitespace on a target
    line, e.g. ``all: \\<TAB>$(EXEC)``.

    A real line-continuation backslash is the LAST character on its line; a
    backslash followed by more text on the same line is an artifact that mangles
    the prerequisite list. Restricted to target-definition lines (``name:``) so
    it never touches a recipe's legitimately-escaped space (``cp a\\ b``).
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    out, changed = [], False
    for line in content.splitlines():
        if re.match(r'^[A-Za-z0-9_.$(){}-]+\s*:', line) and re.search(r'\\[ \t]+\S', line):
            line = re.sub(r'\\[ \t]+(?=\S)', ' ', line)
            changed = True
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out) + '\n')
    return True
