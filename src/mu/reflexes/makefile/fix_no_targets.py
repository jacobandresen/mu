import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_no_targets(f: str) -> bool:
    """Wrap a plain-shell-script Makefile into an all: target."""
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if _TARGET_RE.search(content):
        return False
    recipes = ['\t' + ln.strip() for ln in content.rstrip('\n').splitlines()
               if ln.strip() and not ln.strip().startswith('#')]
    if not recipes:
        return False
    Path(f).write_text('.DEFAULT_GOAL := all\n\nall:\n' + '\n'.join(recipes) + '\n')
    return True
