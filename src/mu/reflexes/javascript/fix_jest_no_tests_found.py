import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_jest_no_tests_found(test_output: str, project_dir: str) -> bool:
    """Add testRegex to package.json when Jest reports 'No tests found'.

    Jest's default testMatch pattern requires `.test.js` / `.spec.js` suffixes.
    When a project uses `_test.js` (Python-style) or another convention, Jest
    exits 1 with 'No tests found'. This reflex broadens the testRegex in
    package.json to match `_test.js` / `_spec.js` in addition to the defaults.
    General: driven entirely by Jest's error message, not any specific project.
    """
    if 'No tests found' not in test_output:
        return False
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    jest_in_scripts = any('jest' in str(v) for v in data.get('scripts', {}).values())
    if 'jest' not in all_deps and not jest_in_scripts:
        return False
    # Already has testRegex or testMatch configured — don't override.
    jest_cfg = data.get('jest', {})
    if jest_cfg.get('testRegex') or jest_cfg.get('testMatch'):
        return False
    # Find actual test files in the project dir to figure out their naming.
    # Match both suffix-style (todo.test.js) and prefix-style (test_todo.js).
    existing = [
        p.name for p in Path(project_dir).iterdir()
        if p.is_file() and (
            re.search(r'[._-](test|spec)\.[jt]sx?$', p.name)
            or (re.match(r'^test_', p.name) and p.suffix.lower() in ('.js', '.jsx', '.mjs', '.ts', '.tsx'))
        )
    ]
    if not existing:
        return False
    # Match suffix-style (.test.js, _test.js) and prefix-style (test_*.js).
    data.setdefault('jest', {})['testRegex'] = r'(test_.*|.*[._-](test|spec))\.[jt]sx?$'
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: added Jest testRegex to {pkg_path} (No tests found)")
    return True
