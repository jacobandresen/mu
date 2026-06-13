import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_extra_closing_brace(file_path: str, test_output: str = '') -> bool:
    """Fix unbalanced braces in JS/TS files when the parser reports a mismatch.

    esbuild / Vitest reports `Unexpected "}"` when a .ts/.js file has more `}`
    than `{`, or `Expected "}" but found ")"` when the reverse is true. This
    reflex counts braces (ignoring strings, template literals, and comments)
    and either removes trailing `}` lines (extra braces) or appends missing
    `}` characters (missing braces). General: applies to any JS/TS file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.ts', '.tsx', '.js', '.jsx'):
        return False
    if test_output and not any(s in test_output for s in
                               ('Unexpected', 'SyntaxError', 'Expected "}"', 'Transform failed')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Count braces AND parens outside strings/comments
    depth = 0  # { vs }
    paren_depth = 0  # ( vs )
    i = 0
    while i < len(text):
        c = text[i]
        # Skip single-line comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        # Skip block comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        # Skip single-quoted string
        if c == "'":
            i += 1
            while i < len(text) and text[i] != "'":
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip double-quoted string
        elif c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip template literal (backtick) — simplified, ignores ${...}
        elif c == '`':
            i += 1
            while i < len(text) and text[i] != '`':
                if text[i] == '\\':
                    i += 1
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth -= 1
        i += 1

    if depth == 0 and paren_depth == 0:
        return False  # already balanced

    # Prefer fixing paren imbalance first (simpler — just remove trailing `)`)
    if paren_depth < 0 and depth == 0:
        # Too many `)`: remove trailing `)` or `))` from the last line
        lines = text.rstrip().splitlines()
        new_lines = list(lines)
        removed = 0
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(paren_depth):
                break
            stripped = new_lines[idx].rstrip()
            if stripped.endswith(')') or stripped.endswith('))'):
                count = min(abs(paren_depth) - removed, stripped.count(')') - stripped.count('('))
                if count > 0:
                    new_lines[idx] = stripped[:-count]
                    removed += count
        if removed:
            Path(file_path).write_text('\n'.join(new_lines) + '\n')
            print(f"==> [mu-agent] Reflex: removed {removed} extra ')' from {file_path}")
            return True

    if depth < 0:
        # Too many `}`: remove or trim trailing `}` lines
        lines = text.rstrip().splitlines()
        removed = 0
        new_lines = list(lines)
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(depth):
                break
            stripped = new_lines[idx].strip()
            # Handle single `}` or `};` lines
            if stripped in ('}', '};'):
                del new_lines[idx]
                removed += 1
            # Handle `}}` or `}};` — remove one `}` at a time from the right
            elif re.match(r'^[}]+;?$', stripped) and len(stripped.rstrip(';')) > 1:
                extra = len(stripped.rstrip(';')) - 1
                to_remove = min(extra, abs(depth) - removed)
                new_stripped = stripped[to_remove:]
                new_lines[idx] = new_stripped
                removed += to_remove
        if not removed:
            return False
        Path(file_path).write_text('\n'.join(new_lines) + '\n')
        print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
        return True
    else:
        # Too many `{`: append `depth` closing braces
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True
