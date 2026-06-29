import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_npm_test_jest(f: str) -> bool:
    """Replace `npm test` or `node *.test.js`/`node *.spec.js` with `npx jest --forceExit` when jest is a devDependency.

    Models write `npm test` or `node x.test.js` in Makefile recipes. `npm test`
    delegates to the package.json test script (`"test": "jest"`). Bare `jest` in a
    shell script is not on PATH; only the npx-resolved binary in node_modules/.bin
    works. Running Jest specs under plain `node` leaves jest globals (describe, it,
    test, jest) undefined. Generic: applies to any Node.js project with jest as a dep.
    """
    if not Path(f).name.lower() == 'makefile':
        return False
    pkg = Path(f).parent / 'package.json'
    if not pkg.exists():
        return False
    try:
        import json as _json
        deps = _json.loads(pkg.read_text())
        all_deps = {**deps.get('dependencies', {}), **deps.get('devDependencies', {})}
    except Exception:
        return False
    if 'jest' not in all_deps:
        return False
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    new_content = content
    # Replace npm test with npx jest --forceExit
    new_content = re.sub(r'(?m)^(\t.*)npm test\b', r'\1npx jest --forceExit', new_content)
    # Replace node <file.test.js> or node <file.spec.js> with npx jest --forceExit
    new_content = re.sub(
        r'(?m)^(\t*)node\s+(\S*[._-]?(test|spec)\.js\S*)',
        r'\1npx jest --forceExit',
        new_content
    )
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced node/npm test with npx jest in {f}")
    return True
