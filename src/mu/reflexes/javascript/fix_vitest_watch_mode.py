import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_vitest_watch_mode(project_dir: str) -> bool:
    """Replace bare `vitest` with `vitest run` in package.json test scripts.

    `vitest` without arguments starts in watch mode and waits for file changes
    indefinitely, causing the test command to hang. `vitest run` executes once
    and exits with a pass/fail code. This fires whenever package.json uses the
    bare `vitest` command as the test script.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        text = pkg.read_text()
        data = json.loads(text)
    except Exception:
        return False
    scripts = data.get('scripts', {})
    changed = False
    for key in list(scripts):
        val = scripts[key]
        if isinstance(val, str) and re.search(r'\bvitest\b(?!\s+run\b)', val):
            scripts[key] = re.sub(r'\bvitest\b(?!\s+run\b)', 'vitest run', val)
            changed = True
    if not changed:
        return False
    data['scripts'] = scripts
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: changed vitest to vitest run in {pkg}")
    return True
