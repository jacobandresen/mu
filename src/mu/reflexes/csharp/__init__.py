"""C# / .NET reflexes: deterministic post-write fixers for C# sources. Split out

One fixer per file (see AGENTS.md §3a); this package re-exports them.
"""

from .fix_csharp_verbatim_string_escape import fix_csharp_verbatim_string_escape
from .fix_csharp_keyword_prefix_artifacts import fix_csharp_keyword_prefix_artifacts
from .fix_csharp_using_order import fix_csharp_using_order
from .fix_csharp_duplicate_classes import fix_csharp_duplicate_classes
from .fix_csharp_missing_using import fix_csharp_missing_using
from .fix_csharp_missing_braces import fix_csharp_missing_braces
from .fix_csharp_xunit_packages import fix_csharp_xunit_packages
from .fix_csharp_consecutive_duplicate_signatures import fix_csharp_consecutive_duplicate_signatures
from .fix_csharp_package_tfm_mismatch import fix_csharp_package_tfm_mismatch
from .fix_csharp_uninstalled_tfm import fix_csharp_uninstalled_tfm
from .fix_csharp_test_program_conflict import fix_csharp_test_program_conflict
from .fix_csharp_lambda_brace_confusion import fix_csharp_lambda_brace_confusion
from .fix_csharp_cross_stage_duplicate_types import fix_csharp_cross_stage_duplicate_types
from .fix_csharp_public_signature_accessibility import fix_csharp_public_signature_accessibility
from .apply_csharp_write_reflexes import apply_csharp_write_reflexes
from .apply_csharp_repair_reflexes import apply_csharp_repair_reflexes

__all__ = [
    'fix_csharp_verbatim_string_escape',
    'fix_csharp_keyword_prefix_artifacts',
    'fix_csharp_using_order',
    'fix_csharp_duplicate_classes',
    'fix_csharp_missing_using',
    'fix_csharp_missing_braces',
    'fix_csharp_xunit_packages',
    'fix_csharp_package_tfm_mismatch',
    'fix_csharp_uninstalled_tfm',
    'fix_csharp_test_program_conflict',
    'fix_csharp_consecutive_duplicate_signatures',
    'fix_csharp_lambda_brace_confusion',
    'fix_csharp_cross_stage_duplicate_types',
    'fix_csharp_public_signature_accessibility',
    'apply_csharp_write_reflexes',
    'apply_csharp_repair_reflexes',
]
