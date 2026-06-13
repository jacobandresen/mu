import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_jest_config_js(project_dir: str) -> bool:
    """Fix jest.config.js files that use JSON syntax instead of CommonJS module syntax.

    Models sometimes write jest.config.js with JSON-style key-value pairs
    (quoted keys, no `module.exports`) which causes `SyntaxError: Unexpected token ':'`.
    If package.json already has a `jest` config section, just delete jest.config.js
    to remove the conflict. Otherwise, wrap the content in `module.exports = {...}`.
    General: any jest.config.js that uses JSON syntax will fail at load time.
    """
    cfg_path = Path(project_dir) / 'jest.config.js'
    if not cfg_path.exists():
        return False
    try:
        text = cfg_path.read_text()
    except OSError:
        return False
    # Detect JSON-style syntax: starts with `{` and uses `"key":` pairs (no module.exports)
    stripped = text.strip()
    if 'module.exports' in text or not stripped.startswith('{'):
        return False
    # If package.json already has a jest config, delete the conflicting file
    pkg_path = Path(project_dir) / 'package.json'
    if pkg_path.exists():
        try:
            import json as _json
            data = _json.loads(pkg_path.read_text())
            if data.get('jest'):
                cfg_path.unlink()
                print("==> [mu-agent] Reflex: removed conflicting jest.config.js (config in package.json)")
                return True
        except Exception:
            pass
    # Otherwise convert JSON-style to CommonJS
    cfg_path.write_text(f'module.exports = {stripped};\n')
    print("==> [mu-agent] Reflex: converted jest.config.js from JSON to CommonJS format")
    return True
