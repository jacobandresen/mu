import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_config_tool_redundant_flag(f: str) -> bool:
    """Remove redundant -L / -I flags that immediately precede a $(shell *-config ...)
    expansion whose output already contains those flags.

    A model commonly writes:
        LDFLAGS = -L $(shell sdl2-config --libs)
    which expands to "-L -L/opt/homebrew/lib -lSDL2", causing a bare "-L" with no
    path and a linker failure. The correct form is just:
        LDFLAGS = $(shell sdl2-config --libs)
    This is a general error with any *-config or pkg-config invocation.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Match: -L or -I (with optional space) immediately before $(shell ...-config
    # or pkg-config invocation). Replace the whole match minus the flag.
    pattern = re.compile(
        r'(-[LI])\s+(\$\(shell\s+(?:pkg-config\b|[a-z0-9_-]+-config\b))',
    )
    new_text, count = pattern.subn(r'\2', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed {count} redundant flag(s) before $(shell *-config) in {f}")
    return True
