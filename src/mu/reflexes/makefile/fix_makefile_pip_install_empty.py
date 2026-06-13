import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_pip_install_empty(f: str) -> bool:
    """Replace bare `pip install` (no packages, no -r) in Makefile recipes.

    Models sometimes write `.venv/bin/pip install ` or `pip install ` with no
    arguments or just whitespace. This raises "You must give at least one
    requirement to install". If a requirements.txt exists, replace with
    `pip install -r requirements.txt`; otherwise add `pytest` as a fallback.
    General: any pip install with no arguments will fail.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    # Match tab-indented pip install lines that have nothing meaningful after 'install'
    pattern = re.compile(r'(?m)^(\t[^\n]*pip\s+install)\s*$')
    if not pattern.search(data):
        return False
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    if req_file:
        replacement = rf'\1 -r {req_file}'
    else:
        replacement = r'\1 pytest'
    new_data = pattern.sub(replacement, data)
    if new_data == data:
        return False
    Path(f).write_text(new_data)
    print(f"==> [mu-agent] Reflex: added package args to bare pip install in {f}")
    return True
