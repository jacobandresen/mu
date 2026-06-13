import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_vue_test_utils_import(file_path: str) -> bool:
    """Replace wrong Vue test utility import sources with @vue/test-utils.

    Models occasionally import `mount` or `shallowMount` from non-existent
    packages like `vue-router-dom`, `@testing-library/vue`, or bare `vue`.
    In Vue 3 + Vitest projects the correct import is always `@vue/test-utils`.
    Fires on any TypeScript/JavaScript test file that mounts Vue components.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.ts', '.tsx', '.js', '.jsx'):
        return False
    stem = Path(file_path).stem.lower()
    if not (stem.endswith('.test') or stem.endswith('.spec') or
            'test' in stem or 'spec' in stem):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fix if the file imports mount/shallowMount/flushPromises from a wrong source
    wrong_sources = (
        r"'vue-router-dom'",
        r'"vue-router-dom"',
        r"'@testing-library/vue'",
        r'"@testing-library/vue"',
        r"from\s+['\"]vue['\"]",   # bare `from 'vue'` when used for mount
    )
    # Check that mount or shallowMount is being imported
    if not re.search(r'\b(mount|shallowMount|flushPromises)\b', text):
        return False
    new_text = text
    for pattern in wrong_sources[:4]:  # literal string replacements
        for fn in ('mount', 'shallowMount', 'flushPromises'):
            new_text = re.sub(
                rf"""(import\s*\{{[^}}]*\b{fn}\b[^}}]*\}})\s*from\s+{pattern}""",
                r"\1 from '@vue/test-utils'",
                new_text,
            )
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: fixed Vue test-utils import in {file_path}")
    return True
