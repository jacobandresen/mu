import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_nested_targets(f: str) -> bool:
    """Lift target definitions accidentally indented inside another recipe.

    Models sometimes indent the entire Makefile under a single ``all:`` block,
    writing ``\thello_world:`` and ``\trun:`` as recipe lines instead of
    top-level targets.  This reflex detects tab-prefixed ``word:`` lines inside
    a recipe and hoists them to column-0 targets.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    lines = content.splitlines()
    if not any(_NESTED_TARGET_RE.match(line) for line in lines):
        return False

    # Rebuild: scan line-by-line; when a misplaced target is found, extract it.
    out: list[str] = []
    extracted: list[list[str]] = []  # each element = [header, *recipe_lines]
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _NESTED_TARGET_RE.match(line)
        if m:
            name = m.group(1)
            deps = m.group(2).strip() if m.group(2) else ''
            header = (name + ': ' + deps) if deps else (name + ':')
            recipe: list[str] = [header]
            i += 1
            seen_cmds: set[str] = set()
            while i < len(lines):
                nxt = lines[i]
                if _NESTED_TARGET_RE.match(nxt):
                    break
                if not nxt.strip():
                    i += 1
                    break
                # Normalise to single-tab indented, deduplicate.
                cmd = '\t' + nxt.lstrip('\t')
                if cmd not in seen_cmds:
                    recipe.append(cmd)
                    seen_cmds.add(cmd)
                i += 1
            extracted.append(recipe)
        else:
            out.append(line)
            i += 1

    if not extracted:
        return False

    # If all: has no prerequisites, add the hoisted target names as deps
    # so `make` actually builds them.
    hoisted_names = [block[0].split(':')[0].strip() for block in extracted]
    all_re = re.compile(r'^(all\s*:)\s*$', re.MULTILINE)
    joined = '\n'.join(out)
    if hoisted_names:
        joined = all_re.sub(r'all: ' + ' '.join(hoisted_names), joined, count=1)

    for block in extracted:
        joined += '\n\n' + '\n'.join(block)

    Path(f).write_text(joined + '\n')
    return True
