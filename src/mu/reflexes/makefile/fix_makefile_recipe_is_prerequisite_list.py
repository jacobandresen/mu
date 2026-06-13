import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_recipe_is_prerequisite_list(f: str) -> bool:
    """Fix a target whose recipe line consists solely of declared target names.

    When `all:` has a recipe `\tinstall test` instead of prerequisites
    `all: install test`, make executes `install test` as a shell command, which
    fails because `install` is a real POSIX binary unrelated to the Makefile.
    This reflex detects recipe lines made up entirely of words that are
    declared targets and converts them to prerequisites on the target line.
    General: applies to any Makefile with this structural mistake.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Find all declared target names.
    declared = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:', content, re.MULTILINE))
    if not declared:
        return False
    # Scan each target: if it has no prerequisites and its FIRST recipe line
    # consists entirely of declared target names, promote them to prerequisites.
    top_re = re.compile(r'^([A-Za-z0-9_.-]+)\s*:\s*$', re.MULTILINE)
    lines = content.splitlines(keepends=True)
    changed = False
    result = []
    i = 0
    while i < len(lines):
        m = top_re.match(lines[i])
        if m:
            target = m.group(1)
            # Peek at the next (recipe) line.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith('\t'):
                recipe = lines[j].strip()
                words = recipe.split()
                # All words must be declared targets AND there must be >0 words.
                known = declared | _KNOWN_TARGETS
                if words and all(w in known for w in words) and words != [target]:
                    # Replace the target line with prerequisites and remove recipe.
                    result.append(f'{target}: {recipe}\n')
                    i += 1  # skip old target line
                    # Skip blank lines
                    while i < len(lines) and not lines[i].strip():
                        result.append(lines[i])
                        i += 1
                    # Skip the recipe line we just promoted.
                    if i < len(lines) and lines[i].startswith('\t'):
                        i += 1
                    changed = True
                    continue
        result.append(lines[i])
        i += 1
    if not changed:
        return False
    Path(f).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: promoted recipe to prerequisites in {f}")
    return True
