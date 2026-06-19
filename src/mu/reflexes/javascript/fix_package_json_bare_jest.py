import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_package_json_bare_jest(project_dir: str) -> bool:
    """Make the package.json `test` script invoke jest correctly, rewriting two
    shapes of the same error to `npx jest --forceExit`:

    1. Bare `jest` (`"test": "jest"`) — not on the shell PATH; the binary lives
       in `node_modules/.bin/` and must be reached via `npx`.
    2. Plain node (`"test": "node todo.test.js"`) — a Jest spec under bare `node`
       has the jest globals (describe/it/test/expect/jest) undefined, so it
       throws `ReferenceError: it is not defined` before any test runs (the
       dominant p8 jest-globals failure).

    Generic: any Node project with jest as a dependency. Also adds testRegex
    proactively (handles `_test.js` naming; survives a repair-model rewrite that
    would drop the one fix_jest_no_tests_found adds reactively).
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
    # A `test` script that runs a Jest spec under plain `node` (`node todo.test.js`)
    # leaves the Jest globals undefined ("it is not defined"). `^node\b` matches the
    # node binary but not `node_modules/.bin/jest`; require a test/spec target so a
    # legitimate `node <app>` runner is left alone.
    elif (test_script and re.match(r'^node\b', test_script)
          and re.search(r'test|spec', test_script, re.I)):
        data.setdefault('scripts', {})['test'] = 'npx jest --forceExit'
        print(f"==> [mu-agent] Reflex: test script ran a Jest spec under plain "
              f"node; switched to npx jest in {pkg_path}")
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
