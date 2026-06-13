import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_package_json_builtin_deps(project_dir: str) -> bool:
    """Remove Node.js core modules from package.json dependencies/devDependencies.

    Node builtins (``fs``, ``path``, ``http`` …) ship with the runtime and are not
    on the npm registry, so listing one as a dependency makes ``npm install`` fail
    with ETARGET / "No matching version found" (observed: the model invents
    ``"fs": "^14.17.0"``). General: a builtin is never a valid npm dependency in
    any Node project — the JS analogue of stripping stdlib names from
    requirements.txt or invalid versions from Cargo.toml.
    """
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    removed: list[str] = []
    for section in ('dependencies', 'devDependencies'):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name in list(deps):
            # Match both bare ("fs") and node:-prefixed ("node:fs") spellings.
            core = name[5:] if name.startswith('node:') else name
            if core in _NODE_CORE_MODULES:
                del deps[name]
                removed.append(name)
        if not deps:
            data.pop(section, None)
    if not removed:
        return False
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: removed Node builtin(s) from {pkg_path}: {removed}")
    return True
