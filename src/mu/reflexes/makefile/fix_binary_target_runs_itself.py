import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_binary_target_runs_itself(f: str) -> bool:
    """Fix a binary target whose recipe runs the binary instead of compiling it.

    Pattern: target ``X:`` with a recipe line that is just ``X`` or ``./X``
    (running the binary, not compiling it), while some other target (e.g. ``all:``)
    holds the actual compile recipe ``cc -o X ...``.  The fix swaps them: the
    compile command moves into ``X:`` and the other target's recipe is cleared so
    it just declares the dependency.

    This is a general-class error — any C/C++ project can exhibit it when the
    model confuses the binary target with a run command.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False

    # Parse into blocks: each block = [header_line, *recipe_lines]
    lines = content.splitlines()
    top_re = re.compile(r'^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:')
    blocks: list[tuple[int, str, list[str]]] = []  # (line_idx, name, recipe_lines)
    i = 0
    while i < len(lines):
        m = top_re.match(lines[i])
        if m and lines[i][0] not in (' ', '\t'):
            name = m.group(1)
            recipe: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].startswith('\t'):
                recipe.append(lines[j])
                j += 1
            blocks.append((i, name, recipe))
            i = j
        else:
            i += 1

    # Find a target X whose sole recipe runs X (bare name or ./X).
    bad_target: tuple[int, str, list[str]] | None = None
    for idx, name, recipe in blocks:
        non_empty = [r.strip() for r in recipe if r.strip()]
        if len(non_empty) == 1 and non_empty[0] in (name, './' + name):
            bad_target = (idx, name, recipe)
            break
    if bad_target is None:
        return False

    _, binary, _ = bad_target

    # Find a compile recipe for `binary` in another target.
    compile_src_idx: int | None = None
    compile_line: str | None = None
    for idx, name, recipe in blocks:
        if name == binary:
            continue
        for r in recipe:
            m2 = re.match(r'^\t.*\b(gcc|clang|cc|g\+\+|clang\+\+)\b.*\s-o\s+' +
                          re.escape(binary) + r'\b', r)
            if m2:
                compile_src_idx = idx
                compile_line = r
                break
        if compile_line:
            break
    if compile_line is None:
        return False

    # Rebuild: put compile_line into binary: and remove it from the source target.
    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = top_re.match(line)
        if m and line[0] not in (' ', '\t'):
            name = m.group(1)
            new_lines.append(line)
            i += 1
            # Collect recipe
            recipe_start = i
            while i < len(lines) and lines[i].startswith('\t'):
                i += 1
            recipe_lines = lines[recipe_start:i]
            if name == binary:
                # Replace run-self recipe with compile command
                new_lines.append(compile_line)
            elif recipe_start - 1 == compile_src_idx:
                # Remove just the compile line from this target's recipe
                new_lines.extend(r for r in recipe_lines if r != compile_line)
            else:
                new_lines.extend(recipe_lines)
        else:
            new_lines.append(line)
            i += 1

    result = '\n'.join(new_lines)
    if result == content:
        return False
    Path(f).write_text(result)
    return True
