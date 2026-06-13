import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_missing_test_target(f: str) -> bool:
    """Add a `test:` phony target when the Makefile has none.

    When `make test` fails with "no rule to make target 'test'", the model
    generated a Makefile without a test target.  Detects the test runner used
    elsewhere in the file (pytest, npm, cargo, go, dotnet) and inserts a
    minimal `test:` target.  Only fires when a recognisable test invocation is
    already present — never guesses.
    """
    try:
        content = Path(f).read_text()
    except OSError:
        return False
    if re.search(r'^test\s*:', content, re.MULTILINE):
        return False  # already has a test target
    # Detect test runner from existing recipes
    if re.search(r'\.venv/bin/pytest', content):
        recipe = '\t.venv/bin/pytest'
    elif re.search(r'\bpytest\b', content):
        recipe = '\tpytest'
    elif re.search(r'\bnpm\s+test\b|\bnpx\s+(?:jest|vitest)\b', content):
        recipe = '\tnpm test'
    elif re.search(r'\bcargo\s+test\b', content):
        recipe = '\tcargo test'
    elif re.search(r'\bdotnet\s+test\b', content):
        recipe = '\tdotnet test'
    elif re.search(r'\bgo\s+test\b', content):
        recipe = '\tgo test ./...'
    else:
        return False
    sep = '' if content.endswith('\n') else '\n'
    Path(f).write_text(content + sep + '\ntest:\n' + recipe + '\n')
    print(f"==> [mu-agent] Reflex: added test: target to {f}")
    return True
