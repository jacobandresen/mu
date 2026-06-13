import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_undefined_imports(file_path: str, lint_error: str) -> bool:
    """Add imports for names reported undefined, by linter OR runtime evidence.

    Recognizes two forms of the same class of error — a name used but never
    imported or defined:
      * pyflakes/flake8 lint:  ``undefined name 'X'`` (F821/F811)
      * Python runtime/pytest: ``NameError: name 'X' is not defined``
    The runtime form matters because a test that uses ``app``/``db`` from the
    implementation module passes a syntax-only lint gate and only fails when
    pytest runs it, so the lint-phase resolver never sees it. For each undefined
    name it searches sibling .py files for a top-level assignment, class, or
    function defining X and adds ``from <module> import X``. Generic: driven
    entirely by the error text and file contents, not any specific problem.
    """
    if not file_path.lower().endswith('.py'):
        return False
    undefined = set(re.findall(r"undefined name '(\w+)'", lint_error))
    undefined |= set(re.findall(r"NameError: name '(\w+)' is not defined", lint_error))
    if not undefined:
        return False
    fp = Path(file_path)
    try:
        text = fp.read_text()
    except OSError:
        return False
    sibling_sources = _sibling_py_sources(file_path)
    to_add = []
    for name in sorted(undefined):
        if re.search(rf'(?:import {re.escape(name)}\b|from \S+ import .*\b{re.escape(name)}\b)', text):
            continue
        for mod, src in sibling_sources.items():
            if re.search(rf'(?m)^(?:class|def)\s+{re.escape(name)}\b', src) or \
               re.search(rf'(?m)^\s*{re.escape(name)}\s*=', src):
                to_add.append((mod, name))
                break
    if not to_add:
        return False
    by_mod: dict[str, list[str]] = {}
    for mod, sym in to_add:
        by_mod.setdefault(mod, []).append(sym)
    stmts = [f"from {mod} import {', '.join(sorted(syms))}" for mod, syms in sorted(by_mod.items())]
    _insert_py_imports(file_path, stmts)
    print(f"==> [mu-agent] Reflex: added undefined-name imports to {file_path}: {stmts}")
    return True
