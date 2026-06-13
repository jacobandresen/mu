import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_unbalanced_braces(file_path: str, build_output: str = '') -> bool:
    """Append or remove closing braces in Rust files with unbalanced brace counts.

    rustc "unclosed delimiter" or "expected `}`" means the file has more `{`
    than `}`. This reflex counts braces (ignoring strings and comments) and
    appends the missing `}` characters.  General: applies to any Rust file.
    """
    if not file_path.endswith('.rs'):
        return False
    if build_output and 'unclosed delimiter' not in build_output and 'expected `}`' not in build_output:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
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
        elif c == '\'':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '\'':
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
    # depth < 0: too many `}` — remove trailing ones
    lines = text.rstrip().splitlines()
    new_lines = list(lines)
    removed = 0
    for idx in range(len(lines) - 1, -1, -1):
        if removed >= abs(depth):
            break
        if new_lines[idx].strip() == '}':
            del new_lines[idx]
            removed += 1
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(new_lines) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
    return True
