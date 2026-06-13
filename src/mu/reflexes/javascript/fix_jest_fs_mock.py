import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_jest_fs_mock(file_path: str) -> bool:
    """Complete a jest.mock('fs', ...) factory that is missing jest.fn() entries.

    When a test does `jest.mock('fs', () => ({ writeFileSync: jest.fn() }))` but
    later calls `fs.readFileSync.mockReturnValue(...)`, the test fails because
    readFileSync wasn't mocked. This reflex detects incomplete fs mock factories
    and ensures all accessed fs methods are included as jest.fn().
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only process files with jest.mock('fs', ...) factory form
    if "jest.mock('fs'" not in text and 'jest.mock("fs"' not in text:
        return False
    # Find which fs methods the test calls .mockReturnValue / .mockResolvedValue / .mockImplementation on
    called_mocks = set(re.findall(r'\bfs\.(\w+)\.mock', text))
    if not called_mocks:
        return False
    # Find the mock factory body and check what's already there
    m = re.search(r"jest\.mock\(['\"]fs['\"],\s*\(\)\s*=>\s*\{(.*?)\}\s*\)",
                  text, re.DOTALL)
    if not m:
        return False
    factory_body = m.group(1)
    missing = [fn for fn in called_mocks if fn not in factory_body]
    if not missing:
        return False
    # Add missing entries before the closing brace of the factory
    additions = ',\n    '.join(f'{fn}: jest.fn()' for fn in sorted(missing))
    # Insert before the last non-whitespace content in the factory body
    new_factory = factory_body.rstrip()
    if new_factory.endswith(','):
        new_factory += f'\n    {additions}'
    else:
        new_factory += f',\n    {additions}'
    new_text = text[:m.start(1)] + new_factory + text[m.end(1):]
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added missing jest.fn() to fs mock in {file_path}")
    return True
