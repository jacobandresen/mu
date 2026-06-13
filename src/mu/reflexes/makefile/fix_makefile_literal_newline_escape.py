import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_literal_newline_escape(f: str) -> bool:
    """Replace literal \\n escape sequences in Makefiles with real newlines.

    Models emit \\n (backslash + n) thinking it means a line break. Strategy:
    \\n\\n → blank line (target boundary), \\n → newline+tab (recipe line).
    After substitution, repair any target-like bare words (no colon, no tab)
    that should be target declarations.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    if '\\n' not in text:
        return False
    new_text = text.replace('\\n\\n', '\n\n')
    new_text = new_text.replace('\\n', '\n\t')
    # Post-pass: fix lines that look like targets missing their colon.
    # A target line has no leading whitespace, a word, and no colon.
    lines = new_text.splitlines()
    result = []
    for ln in lines:
        if ln == '\t':          # lone-tab empty continuation — skip
            continue
        # Bare word at column 0, not a comment, not blank, no colon → add ':'
        if (ln and not ln[0].isspace() and not ln.startswith('#')
                and ':' not in ln and re.match(r'^[A-Za-z_][\w-]*$', ln.strip())):
            ln = ln.rstrip() + ':'
        result.append(ln)
    new_text = '\n'.join(result)
    if new_text == text:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced literal \\n escape(s) in {f}")
    return True
