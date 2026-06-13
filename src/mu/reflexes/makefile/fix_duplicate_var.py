import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_duplicate_var(f: str) -> bool:
    """Remove duplicate top-level variable assignments (keep first)."""
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    var_re = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*[?:+]?=')
    lines, seen, changed, out = data.splitlines(), set(), False, []
    for line in lines:
        m = var_re.match(line)
        if m:
            if m.group(1) in seen:
                changed = True
                continue
            seen.add(m.group(1))
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True
