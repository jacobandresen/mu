import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_env_data_file(file_path: str) -> bool:
    """Convert hardcoded JSON file paths to env-var getter functions for test isolation.

    Two patterns handled:
    A. Module-level `const DATA_FILE = process.env.X || 'default'` — captured at
       load time so Jest beforeEach changes to process.env.X have no effect.
    B. Hardcoded `'./data.json'` or `'todos.json'` etc. inline in function bodies
       with no env-var indirection at all — tests can't override the path.

    Both are converted to `function getDataFile() { return process.env.TODO_FILE || 'data.json'; }`
    with call-sites rewritten to `getDataFile()`, enabling per-test temp-file isolation.
    General: applies to any CommonJS source file used by a test suite.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Skip test files
    stem = Path(file_path).stem.lower()
    if stem.startswith('test_') or stem.endswith('_test') or '.test' in stem or '.spec' in stem:
        return False
    # Skip if already has a getDataFile() or similar getter
    if 'getDataFile' in text or 'getData_file' in text:
        return False

    changed = False
    new_text = text

    # Pattern A: module-level const with env var
    m = re.search(
        r'^(const\s+(\w+)\s*=\s*process\.env\.(\w+)\s*\|\|\s*[\'"][^\'"]+[\'"])\s*;',
        new_text, re.MULTILINE,
    )
    if m:
        const_line, var_name = m.group(1) + ';', m.group(2)
        full_expr = m.group(1).split('=', 1)[1].strip()
        line_start = new_text.rfind('\n', 0, m.start()) + 1
        if not new_text[line_start:m.start()].strip():  # not indented
            parts = var_name.split('_')
            camel = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
            getter_name = 'get' + camel[0].upper() + camel[1:]
            getter_fn = f'function {getter_name}() {{ return {full_expr}; }}'
            new_text = new_text.replace(const_line, getter_fn, 1)
            new_text = re.sub(rf'\b{re.escape(var_name)}\b', f'{getter_name}()', new_text)
            changed = True
            print(f"==> [mu-agent] Reflex: converted {var_name} to {getter_name}() in {file_path}")

    # Pattern B: hardcoded .json path string used in ≥2 function bodies with no env-var override
    if not changed:
        json_paths = re.findall(r'''['"](\.?/?[\w./]*\.json)['"]\s*[,)]''', new_text)
        # Only fire when the same literal path appears multiple times (used in multiple functions)
        from collections import Counter
        counts = Counter(json_paths)
        target = next((p for p, c in counts.items() if c >= 2), None)
        if target:
            env_var = 'TODO_FILE' if 'todo' in target.lower() else 'DATA_FILE'
            getter_fn = f"function getDataFile() {{ return process.env.{env_var} || '{target}'; }}"
            # Replace occurrences in the original text FIRST, then insert getter
            replaced = re.sub(
                rf'''(['"]){re.escape(target)}\1''',
                'getDataFile()',
                new_text,
            )
            replaced = replaced.replace("'getDataFile()'", 'getDataFile()')
            replaced = replaced.replace('"getDataFile()"', 'getDataFile()')
            # Insert getter after the last require() line
            insert_after = max((m.end() for m in re.finditer(r'^.*require\s*\(.*\)\s*;?$', replaced, re.MULTILINE)), default=0)
            insert_pos = replaced.find('\n', insert_after) + 1 if insert_after else 0
            new_text = replaced[:insert_pos] + getter_fn + '\n' + replaced[insert_pos:]
            changed = True
            print(f"==> [mu-agent] Reflex: converted hardcoded '{target}' to getDataFile() in {file_path}")

    if not changed or new_text == text:
        return False
    Path(file_path).write_text(new_text)
    return True
