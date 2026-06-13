import re
import shutil
import subprocess
from pathlib import Path

from ._common import *  # noqa: F401,F403

from .fix_go_missing_pkg_imports import fix_go_missing_pkg_imports
from .fix_go_unused_imports import fix_go_unused_imports

def apply_go_reflexes() -> bool:
    """Resolve Go module dependencies and clean unused imports before a build.

    Generic, problem-agnostic toolchain steps: any Go project with source files
    needs a module file (`go mod init`) and its declared imports fetched
    (`go mod tidy`) — the package manager is the authority on dependency names
    and versions, not the model's guess — and Go's compiler rejects unused
    imports outright, so we let the compiler name them and strip them. Idempotent
    and safe to call repeatedly. Returns True if the go toolchain ran.
    """
    if not shutil.which('go') or not any(Path('.').rglob('*.go')):
        return False
    if not Path('go.mod').exists():
        module = Path.cwd().name or 'app'
        subprocess.run(['go', 'mod', 'init', module], capture_output=True, text=True)
    # tidy adds missing requires (e.g. gin) and writes go.sum; needs network.
    subprocess.run(['go', 'mod', 'tidy'], capture_output=True, text=True, timeout=180)
    fix_go_unused_imports()
    fix_go_missing_pkg_imports()
    return True
