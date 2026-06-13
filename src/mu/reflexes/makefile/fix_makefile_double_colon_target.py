import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_double_colon_target(f: str) -> bool:
    """Fix lines with two colons that make misreads as a static pattern rule.

    `target pattern contains no '%'` means Make saw `A: B: C` and treated
    B as a target pattern. This happens when a model writes the prerequisite
    and recipe on the same target line separated by an extra colon:
        hello_world: main.c: cc -o hello_world main.c
    Fix: strip everything after the second colon and move it to the next line
    as a tab-indented recipe.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    changed = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or line.startswith('\t'):
            out.append(line)
            continue
        # Count colons outside of shell expansions $(...)
        parts = stripped.split(':')
        if len(parts) >= 3 and not stripped.startswith('.'):
            target = parts[0].strip()
            prereq = parts[1].strip()
            recipe = ':'.join(parts[2:]).strip()
            if recipe and not recipe.startswith('='):
                out.append(f'{target}: {prereq}')
                out.append(f'\t{recipe}')
                changed = True
                continue
        out.append(line)
    if not changed:
        return False
    Path(f).write_text('\n'.join(out))
    print(f"==> [mu-agent] Reflex: fixed double-colon target line(s) in {f}")
    return True
