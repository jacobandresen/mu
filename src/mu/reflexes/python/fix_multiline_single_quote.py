import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_multiline_single_quote(file_path: str, lint_error: str) -> bool:
    """Replace multi-line single-quoted SQL strings with triple-quoted strings."""
    if not file_path.endswith('.py') or 'invalid-syntax' not in lint_error:
        return False
    try:
        data = Path(file_path).read_text()
    except OSError:
        return False
    lines = data.splitlines()
    changed, i, result = False, 0, []
    while i < len(lines):
        line = lines[i]
        idx = line.find(".execute('")
        if idx >= 0:
            open_pos = idx + len(".execute(")
            if "'" not in line[open_pos + 1:]:
                line = line[:open_pos] + '"""' + line[open_pos + 1:]
                result.append(line)
                i += 1
                while i < len(lines):
                    inner, stripped = lines[i], lines[i].strip()
                    if stripped.endswith("'')"):
                        close = inner.rfind("'')")
                        inner = inner[:close] + '""")' + inner[close + 3:]
                        changed = True
                        result.append(inner)
                        i += 1
                        break
                    elif stripped.endswith("')"):
                        close = inner.rfind("')")
                        inner = inner[:close] + '""")' + inner[close + 2:]
                        changed = True
                        result.append(inner)
                        i += 1
                        break
                    result.append(inner)
                    i += 1
                continue
        result.append(line)
        i += 1
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result))
    return True
