import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_missing_def(file_path: str) -> bool:
    """Insert a missing `def funcname():` between an orphaned decorator and its body.

    Models occasionally write `@app.route(...)` immediately followed by the
    indented function body, skipping the `def` line entirely. Python raises
    `unexpected indent` on the first body line. This reflex synthesises a
    function name from the route path or decorator name and inserts the def.
    """
    if not file_path.lower().endswith('.py'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    result = []
    changed = False
    used_names: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Collect a block of consecutive decorator lines
        if stripped.startswith('@'):
            decorator_block = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('@'):
                decorator_block.append(lines[j])
                j += 1
            # If the line after the decorators is indented (function body, not def/class)
            if (j < len(lines)
                    and lines[j].startswith((' ', '\t'))
                    and not lines[j].strip().startswith(('def ', 'async def ', 'class '))):
                # Synthesise a unique function name from route path + HTTP methods.
                last_dec = decorator_block[-1].strip()
                path_m = re.search(r"['\"/]([^'\"/?]+)", last_dec)
                method_m = re.search(r"methods\s*=\s*\[([^\]]+)\]", last_dec)
                base = ''
                if path_m:
                    base = re.sub(r'[^a-zA-Z0-9]', '_', path_m.group(1).strip('/'))
                if method_m:
                    methods = re.findall(r"['\"]([A-Z]+)['\"]", method_m.group(1))
                    if methods:
                        base = (base + '_' if base else '') + methods[0].lower()
                name = (base.strip('_') or 'handler')
                # Deduplicate: append suffix if name already used
                candidate, suffix = name, 2
                while candidate in used_names:
                    candidate = f'{name}_{suffix}'
                    suffix += 1
                name = candidate
                used_names.add(name)
                result.extend(decorator_block)
                result.append(f'def {name}():')
                changed = True
                i = j
                continue
            result.extend(decorator_block)
            i = j
            continue
        result.append(line)
        i += 1
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: inserted missing def(s) after orphaned decorator(s) in {file_path}")
    return True
