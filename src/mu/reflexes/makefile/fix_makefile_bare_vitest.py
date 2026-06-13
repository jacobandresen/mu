import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_bare_vitest(f: str) -> bool:
    """Replace bare `vitest` recipe commands with `npx vitest run`.

    vitest is a project-local binary in node_modules/.bin — calling it directly
    in a Makefile recipe fails because it's not on PATH. `npx vitest run` finds
    it in node_modules and runs in non-watch (single-pass) mode.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Match tab-indented lines with `vitest` or `vitest run` not already prefixed with `npx`
    # First handle `vitest run` -> `npx vitest run` (no double 'run')
    new_content = re.sub(
        r'(?m)^(\t[^\n]*)(?<!npx )\bvitest\s+run\b',
        lambda m: m.group(0).replace('vitest run', 'npx vitest run', 1),
        content,
    )
    # Then handle bare `vitest` (not followed by `run` and not preceded by `npx`)
    new_content = re.sub(
        r'(?m)^(\t[^\n]*)(?<!npx )\bvitest\b(?!\s+run\b)(?!\s*:)',
        lambda m: re.sub(r'\bvitest\b(?!\s+run\b)', 'npx vitest run', m.group(0)),
        new_content,
    )
    if new_content == content:
        return False
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced bare vitest with npx vitest run in {f}")
    return True
