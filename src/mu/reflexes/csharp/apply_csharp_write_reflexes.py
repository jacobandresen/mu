import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

from .fix_csharp_consecutive_duplicate_signatures import fix_csharp_consecutive_duplicate_signatures
from .fix_csharp_duplicate_classes import fix_csharp_duplicate_classes
from .fix_csharp_keyword_prefix_artifacts import fix_csharp_keyword_prefix_artifacts
from .fix_csharp_lambda_brace_confusion import fix_csharp_lambda_brace_confusion
from .fix_csharp_missing_braces import fix_csharp_missing_braces
from .fix_csharp_using_order import fix_csharp_using_order
from .fix_csharp_verbatim_string_escape import fix_csharp_verbatim_string_escape

def apply_csharp_write_reflexes(file_path: str) -> None:
    """Write-phase C# chain — preserves the order used in agent.py ~748."""
    if not file_path.endswith('.cs'):
        return
    noted(fix_csharp_lambda_brace_confusion, file_path)
    noted(fix_csharp_keyword_prefix_artifacts, file_path)
    noted(fix_csharp_verbatim_string_escape, file_path)
    noted(fix_csharp_using_order, file_path)
    noted(fix_csharp_consecutive_duplicate_signatures, file_path)
    noted(fix_csharp_missing_braces, file_path)
    noted(fix_csharp_duplicate_classes, file_path)
