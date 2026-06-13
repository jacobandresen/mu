import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_orphan_top_level_commands(f: str) -> bool:
    """Wrap bare commands before the first target into an all: target."""
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if not _TARGET_RE.search(content):
        return False
    lines, seen_target, in_recipe, orphans, clean = content.splitlines(), False, False, [], []
    for line in lines:
        trimmed = line.strip()
        if _TARGET_RE.match(line) and line and line[0] not in ('\t', ' '):
            seen_target = True
            in_recipe = True
            clean.append(line)
        elif line and line[0] == '\t':
            if seen_target:
                in_recipe = True
                clean.append(line)
            else:
                # Tab-indented line before any target — causes "commands commence
                # before first target". Collect as an orphan to wrap into all:.
                orphans.append(line)
        elif not trimmed or trimmed.startswith('#'):
            in_recipe = False
            clean.append(line)
        elif not in_recipe and '=' not in trimmed and not trimmed.startswith('.'):
            orphans.append('\t' + trimmed)
        else:
            clean.append(line)
    if not orphans:
        return False
    all_re = re.compile(r'^all\s*:')
    for line in clean:
        if all_re.match(line):
            result, inserted = [], False
            for ln in clean:
                result.append(ln)
                if not inserted and all_re.match(ln):
                    result.extend(orphans)
                    inserted = True
            Path(f).write_text('\n'.join(result))
            return True
    Path(f).write_text('.DEFAULT_GOAL := all\n\nall:\n' + '\n'.join(orphans) +
                       '\n\n' + '\n'.join(clean))
    return True
