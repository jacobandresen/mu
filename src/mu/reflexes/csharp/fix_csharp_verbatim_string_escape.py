import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_verbatim_string_escape(file_path: str) -> bool:
    """Convert verbatim strings with backslash escapes to regular strings.

    In C# verbatim strings (@"..."), backslash is literal — `\"` does NOT escape
    a quote; it ends the string. Models write `@"{\"key\":value}"` thinking it
    works like a regular string. The fix: drop the `@` prefix so the string
    becomes a regular string where `\"` is valid. The content stays unchanged.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Find @" followed eventually by \" — the verbatim string has invalid escaping.
    # Replace @" with plain " to make it a regular string.
    new_text = re.sub(r'@("(?:[^"\\]|\\.)*")', r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: converted verbatim strings to regular strings in {file_path}")
    return True
