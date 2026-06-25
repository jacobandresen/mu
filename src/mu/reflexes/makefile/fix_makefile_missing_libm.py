import re
from pathlib import Path

from ._common import *  # noqa: F401,F403

# <math.h> functions that glibc keeps in a separate library, so calling them needs `-lm`.
_MATH_FUNCS = re.compile(
    r'\b(sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|exp|exp2|log|log2|log10|'
    r'pow|sqrt|cbrt|ceil|floor|fabs|fmod|hypot|round|trunc|lround|llround)\s*\(')

# A link recipe: a tab-indented recipe line running a C compiler to produce an
# executable (`-o` present). Compile-only steps (`-c`) are excluded below.
_LINK = re.compile(r'^\t.*\b(?:cc|gcc|clang|\$\(CC\)|\$\{CC\})\b.*-o\b')

_SKIP_DIRS = {'obj', 'bin', 'node_modules', '.git', '.venv'}


def fix_makefile_missing_libm(f: str) -> bool:
    """Add `-lm` to the link line when C sources use math functions but the Makefile
    doesn't link libm.

    glibc keeps the `<math.h>` functions (sin/cos/sqrt/...) in a separate library, so a
    program that calls them must link `-lm`. The model writes the SDL2 link
    (`-lSDL2` / `sdl2-config --libs`) but omits `-lm`, so a physics demo fails at link
    with `undefined reference to 'sin'` (×28), `'cos'` (×23), `'sqrt'` — the dominant
    undefined-reference cause across the dojo's physics problems (pendulum, 2D physics).

    Fires when: a C source in the Makefile's tree calls a math function, the Makefile has
    a link recipe (compiler with `-o`, not a `-c` compile step), and `-lm` is absent.
    Appends ` -lm` to those link lines.
    """
    try:
        text = Path(f).read_text()
    except OSError:
        return False
    if '-lm' in text:
        return False

    base = Path(f).parent
    uses_math = False
    for c in list(base.rglob('*.c')) + list(base.rglob('*.h')):
        if any(p in c.parts for p in _SKIP_DIRS):
            continue
        try:
            if _MATH_FUNCS.search(c.read_text(errors='replace')):
                uses_math = True
                break
        except OSError:
            continue
    if not uses_math:
        return False

    out, changed = [], False
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\n')
        if _LINK.search(body) and ' -c ' not in f' {body} ' and '-lm' not in body:
            nl = '\n' if line.endswith('\n') else ''
            out.append(body + ' -lm' + nl)
            changed = True
        else:
            out.append(line)
    if not changed:
        return False
    Path(f).write_text(''.join(out))
    print(f"==> [mu-agent] Reflex: linked libm (-lm) for math functions in {f}")
    return True
