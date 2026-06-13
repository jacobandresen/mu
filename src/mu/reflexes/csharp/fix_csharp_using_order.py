import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_using_order(file_path: str) -> bool:
    """Move all `using` directives to the top of a C# source file.

    CS1529 'A using clause must precede all other elements' fires when using
    statements appear after top-level statements, namespace blocks, or class
    definitions. This reflex collects all using lines and re-emits them at the
    very start of the file before any non-using content.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    using_lines = [ln for ln in lines if ln.lstrip().startswith('using ')]
    non_using_lines = [ln for ln in lines if not ln.lstrip().startswith('using ')]
    if not using_lines:
        return False
    # Check if any using is already out of order (appears after non-empty non-using)
    first_non_using = next((i for i, ln in enumerate(lines)
                            if not ln.lstrip().startswith('using ') and ln.strip()), None)
    first_using_after = any(
        i > first_non_using
        for i, ln in enumerate(lines)
        if ln.lstrip().startswith('using ')
    ) if first_non_using is not None else False
    if not first_using_after:
        return False
    new_text = ''.join(using_lines) + ''.join(non_using_lines)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: moved using statements to top of {file_path}")
    return True
