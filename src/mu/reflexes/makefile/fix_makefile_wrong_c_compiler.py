import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

def fix_makefile_wrong_c_compiler(f: str) -> bool:
    """Replace bare 'c ' as compiler with 'cc ' in Makefile recipe lines.

    Models occasionally write `c $(CFLAGS)` or `c -o binary main.c` where
    `c` is not a valid compiler name (should be `cc` or `clang`). This only
    fires when the recipe line starts with TAB + `c ` followed by typical
    compile flags (-o, -I, -L, -l, $(CC), $(CFLAGS)).
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    pattern = re.compile(r'(?m)^(\t)c +(?=-[oILl]|\$\()')
    new_text, count = pattern.subn(r'\1cc ', text)
    if not count:
        return False
    Path(f).write_text(new_text)
    print(f"==> [mu-agent] Reflex: replaced bare 'c' compiler with 'cc' in {f}")
    return True
