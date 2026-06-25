"""fix_makefile_missing_libm: physics demos call sin/cos/sqrt but the model links only
SDL2 (`-lSDL2`/`sdl2-config --libs`), omitting `-lm` → `undefined reference to 'sin'`
(the dominant undefined-reference cause in the dojo's physics problems). Add `-lm` to the
link recipe when a C source uses a math function and `-lm` is absent.
"""
from pathlib import Path

from mu.reflexes.makefile import fix_makefile_missing_libm


def _proj(tmp_path, makefile, csrc='#include <math.h>\nint main(){ double x = sin(1.0); return (int)x; }\n'):
    (tmp_path / 'main.c').write_text(csrc)
    mf = tmp_path / 'Makefile'
    mf.write_text(makefile)
    return str(mf)


def test_adds_lm_when_math_used_and_absent(tmp_path):
    mf = _proj(tmp_path, "pendulum: main.c\n\tclang -o pendulum main.c -lSDL2\n")
    assert fix_makefile_missing_libm(mf)
    line = [l for l in Path(mf).read_text().splitlines() if '-o pendulum' in l][0]
    assert line.rstrip().endswith('-lm')
    assert not fix_makefile_missing_libm(mf)        # idempotent


def test_noop_when_lm_already_present(tmp_path):
    mf = _proj(tmp_path, "app: main.c\n\tcc -o app main.c -lSDL2 -lm\n")
    assert not fix_makefile_missing_libm(mf)


def test_noop_when_no_math_used(tmp_path):
    mf = _proj(tmp_path, "app: main.c\n\tcc -o app main.c -lSDL2\n",
               csrc='int main(){ return 0; }\n')
    assert not fix_makefile_missing_libm(mf)


def test_skips_compile_only_step(tmp_path):
    # A `-c` compile step must not get -lm; only the link step does.
    mf = _proj(tmp_path,
               "app: main.o\n\tcc -o app main.o -lSDL2\n"
               "main.o: main.c\n\tcc -c -o main.o main.c\n")
    assert fix_makefile_missing_libm(mf)
    text = Path(mf).read_text()
    assert 'cc -o app main.o -lSDL2 -lm' in text
    assert 'cc -c -o main.o main.c -lm' not in text   # compile step untouched
