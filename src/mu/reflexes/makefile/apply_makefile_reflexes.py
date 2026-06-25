import re
import shutil
from pathlib import Path
from mu.reflexes.core import run_reflexes, fix_tool_call_artifacts

from ._common import *  # noqa: F401,F403

from .fix_binary_target_runs_itself import fix_binary_target_runs_itself
from .fix_config_tool_redundant_flag import fix_config_tool_redundant_flag
from .fix_dotnet_test_cwd import fix_dotnet_test_cwd
from .fix_duplicate_var import fix_duplicate_var
from .fix_inline_recipe import fix_inline_recipe
from .fix_makefile_backslash_artifact import fix_makefile_backslash_artifact
from .fix_makefile_bare_pytest import fix_makefile_bare_pytest
from .fix_makefile_bare_vitest import fix_makefile_bare_vitest
from .fix_makefile_double_colon_target import fix_makefile_double_colon_target
from .fix_makefile_escaped_dollar import fix_makefile_escaped_dollar
from .fix_makefile_executable_prerequisites import fix_makefile_executable_prerequisites
from .fix_makefile_literal_newline_escape import fix_makefile_literal_newline_escape
from .fix_makefile_literal_tab_escape import fix_makefile_literal_tab_escape
from .fix_makefile_missing_compile_rule import fix_makefile_missing_compile_rule
from .fix_makefile_missing_libm import fix_makefile_missing_libm
from .fix_makefile_missing_test_target import fix_makefile_missing_test_target
from .fix_makefile_npm_test_jest import fix_makefile_npm_test_jest
from .fix_makefile_pip_install_empty import fix_makefile_pip_install_empty
from .fix_makefile_pip_no_venv import fix_makefile_pip_no_venv
from .fix_makefile_pytest_in_non_python import fix_makefile_pytest_in_non_python
from .fix_makefile_recipe_is_prerequisite_list import fix_makefile_recipe_is_prerequisite_list
from .fix_makefile_sdl2_config_typo import fix_makefile_sdl2_config_typo
from .fix_makefile_space_indent import fix_makefile_space_indent
from .fix_makefile_wrong_c_compiler import fix_makefile_wrong_c_compiler
from .fix_missing_venv_rule import fix_missing_venv_rule
from .fix_nested_targets import fix_nested_targets
from .fix_no_targets import fix_no_targets
from .fix_orphan_top_level_commands import fix_orphan_top_level_commands
from .fix_python_venv_cmd import fix_python_venv_cmd

_MAKEFILE_REFLEXES = [
    # 1. text artifacts
    fix_tool_call_artifacts,
    fix_makefile_literal_tab_escape, fix_makefile_literal_newline_escape,
    fix_makefile_escaped_dollar, fix_makefile_backslash_artifact,
    fix_makefile_wrong_c_compiler, fix_makefile_sdl2_config_typo,
    # 2. structure
    fix_makefile_double_colon_target,
    fix_makefile_space_indent, fix_nested_targets,
    fix_orphan_top_level_commands, fix_no_targets,
    fix_inline_recipe, fix_binary_target_runs_itself,
    fix_makefile_missing_compile_rule,
    fix_makefile_recipe_is_prerequisite_list,
    fix_makefile_executable_prerequisites,
    # 3. recipe/command correctness
    fix_duplicate_var, fix_python_venv_cmd, fix_makefile_pip_no_venv,
    fix_makefile_pip_install_empty, fix_makefile_pytest_in_non_python,
    fix_makefile_bare_pytest, fix_makefile_npm_test_jest, fix_makefile_bare_vitest,
    fix_missing_venv_rule, fix_config_tool_redundant_flag,
    fix_makefile_missing_libm,
    fix_dotnet_test_cwd,
    fix_makefile_missing_test_target,
]

def apply_makefile_reflexes(f: str) -> None:
    """Run the whole Makefile reflex chain over a file to a fixpoint."""
    run_reflexes(_MAKEFILE_REFLEXES, f)
