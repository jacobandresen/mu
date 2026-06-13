import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

from .fix_csharp_keyword_prefix_artifacts import fix_csharp_keyword_prefix_artifacts
from .fix_csharp_lambda_brace_confusion import fix_csharp_lambda_brace_confusion
from .fix_csharp_missing_braces import fix_csharp_missing_braces
from .fix_csharp_missing_using import fix_csharp_missing_using
from .fix_csharp_using_order import fix_csharp_using_order
from .fix_csharp_verbatim_string_escape import fix_csharp_verbatim_string_escape

def apply_csharp_repair_reflexes(file_path: str, test_output: str = '') -> bool:
    """Repair-phase C# chain. Returns True if any reflex changed the file."""
    if not file_path.endswith('.cs'):
        return False
    changed = any([
        noted(fix_csharp_lambda_brace_confusion, file_path),
        noted(fix_csharp_keyword_prefix_artifacts, file_path),
        noted(fix_csharp_verbatim_string_escape, file_path),
        noted(fix_csharp_using_order, file_path),
        noted(fix_csharp_missing_braces, file_path),
        noted(fix_csharp_missing_using, file_path, test_output) if test_output else False,
    ])
    return changed
