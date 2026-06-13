import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_jest_esm(test_output: str, project_dir: str) -> bool:
    """Add NODE_OPTIONS='--experimental-vm-modules' when Jest fails with ESM import errors.

    When a project uses native ESM (package.json "type":"module" or test files with
    import/export syntax), Jest requires the experimental VM modules flag or it dies
    with "Cannot use import statement outside a module". General: any Jest+ESM project
    hits this; it's not specific to any particular test file.
    """
    esm_signals = (
        'Cannot use import statement outside a module',
        'Must use import to load ES Module',
        'Jest encountered an unexpected token',
        'SyntaxError: Unexpected token',
    )
    if not any(sig in test_output for sig in esm_signals):
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
    scripts = data.get('scripts', {})
    jest_in_scripts = any('jest' in str(v) for v in scripts.values())
    if 'jest' not in all_deps and not jest_in_scripts:
        return False
    # Require an ESM project: "type":"module" in package.json or import/export in test files.
    is_esm = data.get('type') == 'module'
    if not is_esm:
        for p in Path(project_dir).glob('*.test.*'):
            try:
                if re.search(r'^\s*(?:import|export)\s', p.read_text(), re.MULTILINE):
                    is_esm = True
                    break
            except OSError:
                pass
    if not is_esm:
        return False
    test_script = scripts.get('test', '')
    if not test_script:
        return False
    if 'experimental-vm-modules' in test_script:
        return False
    data.setdefault('scripts', {})['test'] = (
        f"NODE_OPTIONS='--experimental-vm-modules' {test_script}"
    )
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: added NODE_OPTIONS='--experimental-vm-modules' for Jest ESM in {pkg_path}")
    return True
