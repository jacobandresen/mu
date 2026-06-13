import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls

from ._common import *  # noqa: F401,F403

def fix_rust_cargo_bad_dependency(file_path: str) -> bool:
    """Drop `[dependencies]` entries whose value is not a valid version requirement.

    Small models hallucinate dependencies like ``binary = "fib"`` — a value that
    is not a semver requirement — and `cargo` then fails to even parse the
    manifest ("unexpected character 'f' while parsing major version number"),
    blocking the whole build. Only simple ``name = "value"`` lines inside a
    dependency section are removed, and only when the value cannot be a version
    (does not start with a digit or one of ``^ ~ > < = *``). Real deps
    (``serde = "1"``), table-form deps, and ``[package]`` fields are untouched.
    """
    if Path(file_path).name != 'Cargo.toml':
        return False
    try:
        lines = Path(file_path).read_text().splitlines()
    except OSError:
        return False
    out, in_deps, changed = [], False, False
    for line in lines:
        s = line.strip()
        if s.startswith('['):
            in_deps = s in _CARGO_DEP_SECTIONS
            out.append(line)
            continue
        if in_deps:
            m = _CARGO_DEP_LINE.match(line)
            if m and not re.match(r'^[\d*~^<>=]', m.group(2).strip()):
                changed = True
                continue  # drop the bogus dependency line
        out.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(out) + '\n')
    print(f"==> [mu-agent] Reflex: dropped invalid Cargo.toml dependency in {file_path}")
    return True
