import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

def fix_python_unindented_body(file_path: str, lint_error: str) -> bool:
    """Indent a def/class body the model wrote at the parent's column.

    The model emits `def add_todo():` and then writes the body at column 0;
    every statement until the next top-level construct belongs one level in.
    Driven by the lint message ("expected an indented block after function
    definition on line N"), which names both lines exactly — the largest
    unrecognized repair bucket of the 2026-06-12 run 7 (28 iterations with
    no FOCUS hint). Matches are applied bottom-up so line numbers stay
    valid; the result must parse (ast) or the change is rolled back.
    """
    if not file_path.endswith('.py'):
        return False
    hits = [(int(m['def']), int(m['body'])) for m in
            _UNINDENTED_BODY_RE.finditer(lint_error)
            if m['file'].endswith(Path(file_path).name)]
    if not hits:
        return False
    try:
        original = Path(file_path).read_text()
    except OSError:
        return False
    lines = original.splitlines()
    changed = False
    for def_ln, body_ln in sorted(hits, key=lambda h: -h[1]):
        if not (1 <= def_ln <= len(lines) and 1 <= body_ln <= len(lines)):
            continue
        def_line = lines[def_ln - 1]
        def_indent = len(def_line) - len(def_line.lstrip())
        body_indent = ' ' * (def_indent + 4)
        i = body_ln - 1
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            cur = len(line) - len(line.lstrip())
            # Stop at the next construct at or above the def's own level —
            # a decorator, def/class, or anything once the block has begun.
            if cur <= def_indent and (
                    stripped.startswith(('@', 'def ', 'class ', '#'))
                    or i > body_ln - 1):
                if i > body_ln - 1:
                    break
                if stripped.startswith(('@', 'def ', 'class ')):
                    break
            if cur <= def_indent:
                lines[i] = body_indent + line.lstrip()
                changed = True
            i += 1
    if not changed:
        return False
    new_text = '\n'.join(lines) + ('\n' if original.endswith('\n') else '')
    import ast
    try:
        ast.parse(new_text)
    except SyntaxError:
        return False  # didn't produce valid Python — leave the file alone
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: indented unindented def/class body in {file_path}")
    return True
