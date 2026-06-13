import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_vue_missing_package(project_dir: str) -> bool:
    """Add missing Vue ecosystem packages to package.json devDependencies.

    Two cases:
    1. `vue` itself is missing when `@vitejs/plugin-vue` or `@vue/test-utils` is present.
    2. `@vue/test-utils` is missing when a test file imports from it.
    Generic: any project using these packages needs them in devDependencies.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
    except Exception:
        return False
    dev = data.get('devDependencies', {})
    deps = data.get('dependencies', {})
    all_pkgs = set(list(dev) + list(deps))
    changed = False

    # Case 1: add `vue` when @vue/* or plugin-vue is present but vue itself is absent
    needs_vue = any(k.startswith('@vue/') or k == '@vitejs/plugin-vue' for k in all_pkgs)
    has_vue = 'vue' in all_pkgs
    if needs_vue and not has_vue:
        dev['vue'] = '^3.4.0'
        changed = True
        print(f"==> [mu-agent] Reflex: added missing vue package to {pkg}")

    # Case 2: add `@vue/test-utils` when a test file imports it but it's not in package.json
    has_test_utils = '@vue/test-utils' in all_pkgs
    if not has_test_utils:
        test_files = list(Path(project_dir).rglob('*.test.ts')) + \
                     list(Path(project_dir).rglob('*.test.js')) + \
                     list(Path(project_dir).rglob('*.spec.ts'))
        for tf in test_files:
            if 'node_modules' in str(tf):
                continue
            try:
                if '@vue/test-utils' in tf.read_text():
                    dev['@vue/test-utils'] = '^2.4.0'
                    changed = True
                    print(f"==> [mu-agent] Reflex: added missing @vue/test-utils to {pkg}")
                    break
            except OSError:
                pass

    if not changed:
        return False
    data['devDependencies'] = dev
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    return True
