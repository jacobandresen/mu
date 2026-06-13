import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_pip_no_venv(f: str) -> bool:
    """Rewrite Makefiles that do bare 'pip install' then bare 'pytest' to use a venv.

    'pip install -r requirements.txt && pytest' installs packages into whichever
    Python owns the current pip, but 'pytest' may use a different interpreter.
    This produces ModuleNotFoundError at collection. The fix: replace the install
    recipe with a .venv-based pattern and rewrite bare 'pytest' to '.venv/bin/pytest'.
    Only fires when the Makefile has pip install AND bare pytest AND no venv yet.
    """
    try:
        data = Path(f).read_text()
    except OSError:
        return False
    has_pip = bool(re.search(r'(?m)^\t.*\bpip\b.*install\b', data))
    has_bare_pytest = bool(re.search(r'(?m)^\t.*(?<!\/)pytest\b', data))
    has_venv = '.venv' in data
    if not (has_pip and has_bare_pytest) or has_venv:
        return False

    # Replace bare `pip` with `.venv/bin/pip` and bare `pytest` with `.venv/bin/pytest`
    new_data = re.sub(r'(?m)^(\t.*)\bpip\b', r'\1.venv/bin/pip', data)
    new_data = re.sub(r'(?m)^(\t.*)(?<!\/)pytest\b', r'\1.venv/bin/pytest', new_data)

    # Insert venv creation before the first recipe that uses pip/pytest
    req_file = 'requirements.txt' if Path(f).parent.joinpath('requirements.txt').exists() else ''
    pip_install = (f'\t.venv/bin/pip install -r {req_file} pytest'
                   if req_file else '\t.venv/bin/pip install pytest')
    venv_block = f'\n.venv:\n\tpython3 -m venv .venv\n{pip_install}\n'

    # Add .venv as prerequisite of targets that now reference .venv/bin/
    top_re = re.compile(r'(?m)^([A-Za-z0-9_./-][A-Za-z0-9_./-]*)\s*:([^=\n]*)$')
    def add_venv_dep(m):
        name, prereqs = m.group(1), m.group(2).strip()
        if name == '.venv':
            return m.group(0)
        return f'{name}: .venv {prereqs}'.rstrip()
    new_data = top_re.sub(add_venv_dep, new_data)
    new_data += venv_block

    Path(f).write_text(new_data)
    print(f"==> [mu-agent] Reflex: rewrote Makefile to use .venv in {f}")
    return True
