import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_inline_recipe(f: str) -> bool:
    """Split inline recipes (target: command) onto separate lines."""
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    declared = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', data, re.MULTILINE))
    lines, changed, out = data.splitlines(), False, []
    for line in lines:
        trimmed = line.strip()
        if (line and line[0] != '\t' and not trimmed.startswith('#') and
                not trimmed.startswith('.') and '=' not in trimmed):
            colon = trimmed.find(':')
            if colon > 0 and colon < len(trimmed) - 1:
                target, after = trimmed[:colon].strip(), trimmed[colon + 1:].strip()
                is_known = target in _KNOWN_TARGETS
                is_compiler = _INLINE_COMPILER_RE.match(after)
                if (is_known or is_compiler) and ' ' in after and not after.startswith('='):
                    # If every word after the colon is a declared target or a known
                    # target name, this is a prerequisite list — leave it alone.
                    # fix_makefile_recipe_is_prerequisite_list uses declared|_KNOWN_TARGETS
                    # as its promotion set; using the same set here prevents oscillation
                    # when words like 'install'/'test' are in _KNOWN_TARGETS but not
                    # explicitly declared as targets in this file.
                    if all(w in (declared | _KNOWN_TARGETS) for w in after.split()):
                        out.append(line)
                        continue
                    out.extend([target + ':', '\t' + after])
                    changed = True
                    continue
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    return True
