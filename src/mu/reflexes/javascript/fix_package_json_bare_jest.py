import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_package_json_bare_jest(project_dir: str) -> bool:
    """Replace bare `jest` in package.json scripts.test with `npx jest --forceExit`.
    Also sets testRegex to match both `.test.js` and `_test.js` naming conventions.

    When a model writes `"test": "jest"` in package.json scripts, running
    `npm test` invokes `jest` directly which is not on the shell PATH. The
    locally-installed binary lives in `node_modules/.bin/` and must be reached
    via `npx`. Generic: applies to any project with jest as a dependency.

    Also adds testRegex proactively to handle `_test.js` naming (Python-style).
    Doing this at write time rather than reactively prevents the repair model
    from reverting the testRegex added by fix_jest_no_tests_found.
    """
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    scripts = data.get('scripts', {})
    jest_in_scripts = any('jest' in str(v) for v in scripts.values())
    if 'jest' not in all_deps and not jest_in_scripts:
        return False
    changed = False
    test_script = scripts.get('test', '')
    # Replace bare `jest` (with or without flags, but not already prefixed with npx)
    if test_script and 'npx' not in test_script and re.match(r'^jest\b', test_script):
        new_script = re.sub(r'^jest\b', 'npx jest', test_script)
        if '--forceExit' not in new_script:
            new_script = new_script.rstrip() + ' --forceExit'
        data.setdefault('scripts', {})['test'] = new_script
        print(f"==> [mu-agent] Reflex: replaced bare jest with npx jest in {pkg_path}")
        changed = True
    # Also proactively add testRegex to handle _test.js and test_*.js naming conventions
    jest_cfg = data.get('jest', {})
    correct_regex = r'(test_.*|.*[._-](test|spec))\.[jt]sx?$'
    if not jest_cfg.get('testRegex') or jest_cfg.get('testRegex') == '':
        data.setdefault('jest', {})['testRegex'] = correct_regex
        print(f"==> [mu-agent] Reflex: added testRegex to jest config in {pkg_path}")
        changed = True
    if not changed:
        return False
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    return True
