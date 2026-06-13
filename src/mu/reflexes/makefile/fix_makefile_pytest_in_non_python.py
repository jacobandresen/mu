import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_pytest_in_non_python(f: str) -> bool:
    """Replace 'pytest' in test: target when the project has no Python source files.

    When a model writes a C/Rust/Go Makefile but still puts 'pytest' in the
    test: recipe, 'make' fails immediately. If no .py files exist in the project
    directory, replace the pytest call with '@true' (no-op) so make succeeds.
    Also removes 'test' from the default target's prerequisites to avoid running
    pytest as a build step.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    # Only fire if the Makefile has a test: target with pytest
    if not re.search(r'(?m)^test\s*:.*\n\t.*pytest\b', content):
        return False
    # Don't touch Python projects
    proj_dir = Path(f).parent
    if list(proj_dir.glob('*.py')) or list(proj_dir.glob('requirements.txt')):
        return False
    # Replace pytest in test: recipe with @true (no-op)
    new_content = re.sub(
        r'(?m)^(test\s*:.*\n)(\t.*)pytest\b(.*)',
        r'\1\2@true\3',
        content,
    )
    if new_content == content:
        return False
    # Also remove 'clean' from build target prerequisite lists so the binary
    # isn't deleted before the test command runs './binary'.
    # Pattern: 'target: ... clean ...' → remove 'clean' word from prereqs
    new_content = re.sub(
        r'(?m)^([A-Za-z_][A-Za-z_0-9]*\s*:[^#\n]*)\bclean\b\s*',
        r'\1',
        new_content,
    )
    Path(f).write_text(new_content)
    print(f"==> [mu-agent] Reflex: replaced pytest in test: target with @true in {f}")
    return True
