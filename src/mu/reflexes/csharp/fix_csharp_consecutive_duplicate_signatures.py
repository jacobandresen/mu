import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_consecutive_duplicate_signatures(file_path: str) -> bool:
    """Drop repeated copies of a method-signature line stuttered by the model.

    Degenerate generations emit the same opener several times before the
    body arrives::

        [Fact]
        public void TestFib() {
        public void TestFib() {     <- never valid C#
                [Fact]
        public void TestFib() {

    Two identical signature openers with nothing but blank/attribute lines
    between them cannot be valid C# (the first body would have to start
    first), so removing the duplicates — and the orphaned attributes glued
    to them — is safe. Dominant failure bucket of the 2026-06-12 run-4
    collection (4 sessions, CS1513/CS0111 storms the repair loop never
    recovered from).
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        lines = Path(file_path).read_text().splitlines()
    except OSError:
        return False
    out: list[str] = []
    removed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        if not _CS_SIG_RE.match(line):
            continue
        sig = line.strip()
        # Swallow any chain of {blank/attribute}* + identical signature.
        while True:
            j = i
            while j < len(lines) and (not lines[j].strip()
                                      or _CS_ATTR_RE.match(lines[j])):
                j += 1
            if j < len(lines) and lines[j].strip() == sig:
                removed += (j + 1) - i
                i = j + 1  # drop the in-between attrs/blanks and the duplicate
            else:
                break
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(out) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} stuttered duplicate "
          f"signature line(s) from {file_path}")
    return True
