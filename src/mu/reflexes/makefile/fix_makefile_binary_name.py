import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_binary_name(f: str, test_cmd: str) -> bool:
    """Rename the Makefile's output binary to match what the test command expects.

    When the test command is `make && ./foo` but the Makefile builds `bar`, the
    compiled binary exists but the test can't find it. This reflex renames the
    Makefile target and -o flag to match the expected binary name.
    General: applies to any compiled-language Makefile, not SDL2-specific.
    """
    if not test_cmd:
        return False
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    # Extract expected binary from test command: `./name` or bare `name` after `make &&`
    m = re.search(r'&&\s+\.?/?([\w.-]+)\s*$', test_cmd)
    if not m:
        return False
    expected = m.group(1)
    # Find the actual -o target in the Makefile
    o_match = re.search(r'-o\s+([\w.-]+)', text)
    if not o_match:
        return False
    actual = o_match.group(1)
    if actual == expected:
        return False
    # Rename: replace all occurrences of the actual binary name as a whole word
    new_text = re.sub(rf'\b{re.escape(actual)}\b', expected, text)
    if new_text == text:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: renamed Makefile binary '{actual}' → '{expected}' in {f}")
    return True
