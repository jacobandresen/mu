import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_escaped_dollar(f: str) -> bool:
    r"""Replace \$(cmd) patterns in Makefile recipes with $(cmd) or bare cmd.

    Models sometimes write `\$(npm) install` thinking it calls npm. In a
    Makefile recipe `\$` means a literal `$`, so the shell receives `$(npm)
    install` where `$(npm)` is a command-substitution — empty for npm — leaving
    just ` install` which fails. Replace `\$(npm)` with `npm`, `\$(node)` with
    `node`, `\$(python)` with `python3`, and `\$(make)` with `$(MAKE)`.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if r'\$(' not in content:
        return False
    replacements = {
        r'\$(npm)': 'npm',
        r'\$(node)': 'node',
        r'\$(python3)': 'python3',
        r'\$(python)': 'python3',
        r'\$(make)': '$(MAKE)',
        r'\$(cargo)': 'cargo',
        r'\$(go)': 'go',
    }
    new_content = content
    for bad, good in replacements.items():
        new_content = new_content.replace(bad, good)
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced escaped \\$(...) with direct commands in {f}")
    return True
