import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_sqlite_class_missing_init_table(file_path: str) -> bool:
    """Call the table-creation method from __init__ when it's missing.

    LLMs write a TodoManager/Database class that defines a _create_table() /
    init_db() / setup() method containing `CREATE TABLE IF NOT EXISTS`, but
    forget to call it in __init__ — causing sqlite3.OperationalError: no such
    table on the first SQL operation. This reflex detects that gap and inserts
    the call at the end of __init__ (before the closing indent).

    Only fires on non-test .py files. Safe: the CREATE TABLE is idempotent due
    to IF NOT EXISTS, so a double-call is harmless.
    """
    if not file_path.lower().endswith('.py'):
        return False
    base = Path(file_path).name
    if base.startswith('test_') or '_test.' in base:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    if 'sqlite3' not in text or 'CREATE TABLE' not in text.upper():
        return False

    lines = text.splitlines(keepends=True)

    # Walk lines to find class methods and their bodies using indentation.
    # Build: method_name → set of lines in its body.
    # Then find which methods contain CREATE TABLE and are NOT __init__.
    def _parse_methods(lines):
        """Yield (indent, name, start_line, body_lines[]) for each def in a class body."""
        i = 0
        while i < len(lines):
            m = re.match(r'^(\s*)def\s+(\w+)\s*\(', lines[i])
            if m:
                indent, name = m.group(1), m.group(2)
                body = []
                j = i + 1
                while j < len(lines):
                    ln = lines[j]
                    stripped = ln.lstrip()
                    if not stripped or stripped.startswith('#'):
                        body.append(ln)
                        j += 1
                        continue
                    curr_indent = len(ln) - len(ln.lstrip())
                    if curr_indent <= len(indent):
                        break
                    body.append(ln)
                    j += 1
                yield indent, name, i, body, j  # j = first line after body
            i += 1

    methods = list(_parse_methods(lines))

    # Find methods (not __init__) that contain CREATE TABLE
    create_methods = []
    for indent, name, start, body, end in methods:
        if name == '__init__':
            continue
        body_text = ''.join(body)
        if re.search(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS', body_text, re.IGNORECASE):
            create_methods.append(name)

    if not create_methods:
        return False

    # Find __init__ and check if it calls any create method
    for indent, name, start, body, end in methods:
        if name != '__init__':
            continue
        body_text = ''.join(body)
        for cm in create_methods:
            if re.search(rf'\bself\.{re.escape(cm)}\s*\(', body_text):
                return False  # already called

        # Add the call at the end of __init__ body
        body_indent = indent + '    '
        call_line = f'{body_indent}self.{create_methods[0]}()\n'
        new_lines = lines[:end] + [call_line] + lines[end:]
        Path(file_path).write_text(''.join(new_lines))
        print(f"==> [mu-agent] Reflex: added self.{create_methods[0]}() call in __init__ of {file_path}")
        return True

    return False
