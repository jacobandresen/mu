import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_missing_pip_packages(test_output: str, project_dir: str) -> bool:
    """Add missing pip packages to requirements.txt when tests fail with ModuleNotFoundError.

    Parses 'ModuleNotFoundError: No module named X' from test output, maps X to
    its pip package name, and adds it to requirements.txt (creating the file if
    needed). Generic: driven entirely by the error message, not any specific problem.
    """
    missing = re.findall(r"ModuleNotFoundError: No module named '([^']+)'", test_output)
    if not missing:
        return False
    # Normalise: take the top-level package name (e.g. 'flask_sqlalchemy.X' → 'flask_sqlalchemy')
    pkgs = {m.split('.')[0] for m in missing}
    # Skip stdlib
    pkgs -= _STDLIB_MODULES
    if not pkgs:
        return False
    req_path = Path(project_dir) / 'requirements.txt'
    try:
        existing = req_path.read_text() if req_path.exists() else ''
    except OSError:
        existing = ''
    existing_lower = existing.lower()
    to_add = [
        pip_name
        for pkg in sorted(pkgs)
        for pip_name in [_PIP_NAME.get(pkg, pkg.replace('_', '-'))]
        if pip_name.lower() not in existing_lower
    ]
    if not to_add:
        return False
    existing_lines = [line for line in existing.splitlines() if line.strip()]
    new_content = '\n'.join(existing_lines + to_add) + '\n'
    req_path.write_text(new_content)
    print(f"==> [mu-agent] Reflex: added missing packages to requirements.txt: {to_add}")
    return True
