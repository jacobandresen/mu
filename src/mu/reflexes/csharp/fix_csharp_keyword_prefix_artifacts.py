import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_keyword_prefix_artifacts(file_path: str) -> bool:
    """Remove stray 1-2 char prefix artifacts glued to C# keywords at line start.

    Models occasionally emit `tnamespace`, `#class`, etc. — a lone character
    fused to a keyword. The `t` before `namespace` causes CS1513/CS1022.
    Pattern: line starts with 1-2 lowercase letters OR a non-letter char,
    immediately followed (no space) by a known keyword + word boundary.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    kws = (r'namespace|class|struct|interface|enum|public|private|protected|'
           r'internal|using|static|abstract|sealed|partial|record')
    # Match 1-2 lowercase letters OR one symbol, fused directly to a keyword
    pattern = re.compile(r'^(?:[a-z]{1,2}|[^a-zA-Z\s])(' + kws + r')\b', re.MULTILINE)
    new_text = pattern.sub(r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed keyword prefix artifact(s) in {file_path}")
    return True
