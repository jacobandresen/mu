import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_literal_tab_escape(f: str) -> bool:
    """Remove/replace literal \\t and \\@ escape sequences in Makefiles.

    Models sometimes write \\t (backslash + t) thinking it means TAB, and \\@
    thinking it silences a recipe line. In Makefiles these are literal characters.

    Cases handled:
    - Line starts with \\t: replace with real TAB (recipe indentation).
    - Line starts with \\@: replace with real TAB + @ (silent recipe).
    - \\t inside a variable or recipe line: replace with space.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    if '\\t' not in text and '\\@' not in text:
        return False
    lines = text.splitlines()
    changed = False
    out = []
    for line in lines:
        if line.startswith('\\@'):
            out.append('\t@' + line[2:])
            changed = True
        elif line.startswith('\\t'):
            out.append('\t' + line[2:])
            changed = True
        elif line.startswith('\t\\@'):
            # Real tab followed by \@ — convert \@ to @ (already has proper indent)
            out.append('\t@' + line[3:])
            changed = True
        elif '\\t' in line:
            new_line = line.replace('\\t', ' ')
            out.append(new_line)
            changed = True
        else:
            out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: removed literal \\t escape(s) in {f}")
    return True
