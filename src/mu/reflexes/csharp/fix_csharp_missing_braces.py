import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_missing_braces(file_path: str) -> bool:
    """Append missing closing braces to C# files with unbalanced brace counts.

    CS1513 '} expected' means the file has more `{` than `}`. This reflex counts
    braces (ignoring strings and comments) and appends the missing `}` characters.
    General: applies to any C# file, not specific to any program.
    """
    if not file_path.lower().endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Count braces outside strings and single-line comments
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Single-line comment — skip to end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if c == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    if depth == 0:
        return False
    if depth > 0:
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True
    # depth < 0: too many `}` — remove trailing standalone `}` lines
    lines = text.rstrip().splitlines()
    new_lines = list(lines)
    removed = 0
    for idx in range(len(lines) - 1, -1, -1):
        if removed >= abs(depth):
            break
        stripped = new_lines[idx].strip()
        if stripped == '}':
            del new_lines[idx]
            removed += 1
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(new_lines) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
    return True
