import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_vitest_globals(project_dir: str, test_output: str) -> bool:
    """Enable Vitest globals when test output reports 'test is not defined'.

    Vitest does not expose test/expect/describe as globals by default. Without
    `globals: true` in vite.config.ts, calling test(...) raises ReferenceError.
    This reflex adds globals: true to the test config block. General: any Vitest
    project that uses bare test() calls needs globals enabled.
    """
    if 'is not defined' not in test_output and 'ReferenceError' not in test_output:
        return False
    if not any(name in test_output for name in ('test', 'expect', 'describe', 'beforeEach', 'it')):
        return False
    config_path = Path(project_dir) / 'vite.config.ts'
    if not config_path.exists():
        config_path = Path(project_dir) / 'vite.config.js'
    if not config_path.exists():
        return False
    try:
        text = config_path.read_text()
    except OSError:
        return False
    if 'globals: true' in text or "globals:true" in text:
        return False
    # Add globals: true inside the test: { ... } block
    new_text = re.sub(
        r'(test\s*:\s*\{)',
        r'\1\n    globals: true,',
        text,
        count=1,
    )
    if new_text == text:
        # No test block found — append a minimal one
        if 'test:' not in text:
            new_text = re.sub(
                r'(export default defineConfig\(\{)',
                r'\1\n  test: { environment: "jsdom", globals: true },',
                text,
                count=1,
            )
    if new_text == text:
        return False
    config_path.write_text(new_text)
    print(f"==> [mu-agent] Reflex: added Vitest globals:true to {config_path}")
    return True
