import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_sdl2_config_typo(f: str) -> bool:
    """Fix common misspellings of sdl2-config in Makefiles.

    Models occasionally write 'sdl2-cconfig', 'sdl2config', 'SDL2-config', etc.
    The correct tool name is exactly 'sdl2-config'.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Fix common typo variants
    pattern = re.compile(r'\bsdl2-cconfig\b|\bsdl2config\b|\bSDL2-config\b|\bsdl2-Config\b', re.IGNORECASE)
    new_text, count = pattern.subn('sdl2-config', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: fixed sdl2-config typo in {f}")
    return True
