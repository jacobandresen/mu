import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

def fix_csharp_lambda_brace_confusion(file_path: str) -> bool:
    """Replace {){ artifacts from mis-nested C# lambda chains.

    Models sometimes close a nested lambda chain with `{){` instead of the
    correct closing parens.  E.g.:
        s.AddDbContext<AppDb>(o => o.UseSqlite("..."))){){
    `{){` is never valid C# in this position; substituting `))` re-balances the
    expression so the repair model can fix any remaining semantic error.
    """
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    cleaned = re.sub(r'\{\s*\)\s*\{', '))', text)
    if cleaned == text:
        return False
    Path(file_path).write_text(cleaned)
    print(f"==> [mu-agent] Reflex: removed {{){{ lambda artifact in {file_path}")
    return True
