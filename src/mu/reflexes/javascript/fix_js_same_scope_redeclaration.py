import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted

from ._common import *  # noqa: F401,F403

def fix_js_same_scope_redeclaration(file_path: str, test_output: str = '') -> bool:
    """Convert a same-scope re-declaration (`const X = ...` twice in one block)
    into a plain assignment.

    Babel/Jest dies with "Identifier 'X' has already been declared" when a test
    re-declares a let/const name in the same block — observed pattern: the model
    re-reads state mid-test with a fresh `const todos = readTodos();` instead of
    assigning to the existing variable. fix_js_duplicate_const only removes
    *consecutive exact duplicate* lines; here the conflicting declaration sits
    several lines up. The later declaration loses its keyword (becoming an
    assignment) and the first one is promoted from `const` to `let` so the
    assignment is legal. Scope is tracked by brace depth with strings and
    comments skipped, so legal shadowing in an inner block is left alone.
    General: re-declaring a let/const name in one block is always a JS syntax
    error, in any file.
    """
    if test_output and 'has already been declared' not in test_output:
        return False
    if Path(file_path).suffix.lower() not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    decl_re = re.compile(r'^(\s*)(const|let|var)\s+([A-Za-z_$][\w$]*)(\s*=[^=>].*)$')
    lines = text.splitlines(keepends=True)
    # Scope stack: each frame maps a declared name -> (line index, keyword).
    scopes: list[dict[str, tuple[int, str]]] = [{}]
    in_block_comment = False
    in_template = False
    changed = False

    for idx, line in enumerate(lines):
        if not in_block_comment and not in_template:
            m = decl_re.match(line)
            if m:
                indent, kw, name, rest = m.groups()
                prior = scopes[-1].get(name)
                # `var x` twice is legal JS; any let/const involvement is not.
                if prior and not (kw == 'var' and prior[1] == 'var'):
                    first_idx = prior[0]
                    nl = '\n' if line.endswith('\n') else ''
                    lines[idx] = f'{indent}{name}{rest}{nl}'
                    lines[first_idx] = re.sub(r'^(\s*)const\b', r'\1let',
                                              lines[first_idx], count=1)
                    changed = True
                elif not prior:
                    scopes[-1][name] = (idx, kw)
        # Update brace depth, skipping strings and comments.
        i = 0
        while i < len(line):
            c = line[i]
            if in_block_comment:
                if c == '*' and i + 1 < len(line) and line[i + 1] == '/':
                    in_block_comment = False
                    i += 1
            elif in_template:
                if c == '\\':
                    i += 1
                elif c == '`':
                    in_template = False
            elif c == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break  # rest of line is a comment
            elif c == '/' and i + 1 < len(line) and line[i + 1] == '*':
                in_block_comment = True
                i += 1
            elif c in ('"', "'"):
                quote = c
                i += 1
                while i < len(line) and line[i] != quote:
                    if line[i] == '\\':
                        i += 1
                    i += 1
            elif c == '`':
                in_template = True
            elif c == '{':
                scopes.append({})
            elif c == '}':
                if len(scopes) > 1:
                    scopes.pop()
            i += 1

    if not changed:
        return False
    Path(file_path).write_text(''.join(lines))
    print(f"==> [mu-agent] Reflex: converted same-scope re-declaration(s) to assignment in {file_path}")
    return True
