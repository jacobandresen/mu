import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_bare_pytest(f: str) -> bool:
    """Replace bare 'pytest' with '.venv/bin/pytest' in Makefile recipes that use a venv.

    When a Makefile creates a .venv for the project, test recipes must use
    .venv/bin/pytest — bare 'pytest' uses the system pytest which lacks the
    installed packages, producing ModuleNotFoundError at collection time.
    Only rewrites when the Makefile already references .venv (install step
    creates it), to avoid changing Makefiles that intentionally use system pytest.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if '.venv' not in content:
        return False
    # Only replace bare 'pytest' — skip lines that already have .venv/bin/pytest
    # or that contain a package manager command (pip install pytest).
    pattern = re.compile(r'(?m)^(\t(?!.*\.venv/bin/)(?!.*\bpip\b).*\b)pytest(\b)')
    new_content = pattern.sub(r'\1.venv/bin/pytest\2', content)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced bare pytest with .venv/bin/pytest in {f}")
    return True
