"""Reflex catalog: machine-readable metadata for every reflex.

The reflex functions live in the per-language modules; this module gives each a
*record* — the schema from docs/REFLEX_KB.md §3 — so the reflex layer becomes
queryable (which exist, what class, what trigger) and analysable (the SQLite KB
in reflexdb.py joins firings against these records).

Most attributes are derived automatically so they never drift from the code:
``toolchain`` from the module, ``trigger``/``scope`` from the function signature.
Only ``error_class`` (and the occasional ``risk`` override) is curated — kept in
one readable table below, grouped by class so the cross-toolchain families are
visible at a glance.
"""

import inspect
from dataclasses import dataclass

from mu import reflexes

# Per-language modules to scan for public ``fix_*`` / ``apply_*`` reflexes.
_MODULES = ('core', 'python', 'rust', 'csharp', 'go', 'javascript',
            'makefile', 'plan_reflexes')

# ── curated: reflex id → error_class, grouped by class (the §4 taxonomy) ──────
# Cross-toolchain families are obvious here: dependency-hygiene spans cargo/pip/
# npm, duplicate-declaration spans rust/js/csharp, etc.
_CLASS_MEMBERS: dict[str, list[str]] = {
    'dependency-hygiene': [
        'fix_rust_cargo_bad_dependency', 'fix_requirements_stdlib_entries',
        'fix_requirements_path_entries', 'fix_package_json_builtin_deps',
        'fix_makefile_pip_install_empty'],
    'duplicate-declaration': [
        'fix_rust_duplicate_use', 'fix_js_duplicate_require',
        'fix_csharp_duplicate_classes', 'fix_duplicate_var'],
    'missing-symbol-import': [
        'fix_python_undefined_imports', 'fix_python_missing_project_imports',
        'fix_python_missing_stdlib_imports', 'fix_js_missing_requires',
        'fix_go_missing_pkg_imports', 'fix_csharp_missing_using',
        'fix_rust_missing_trait_import', 'fix_test_import_module'],
    'unused-import': ['fix_go_unused_imports'],
    'test-isolation': [
        'fix_sqlite_test_isolation', 'fix_sqlite_memory_multi_connect',
        'fix_missing_flask_client_fixture', 'fix_jest_fs_mock',
        'fix_sqlite_missing_row_factory', 'fix_sqlite_path_unlink'],
    'test-command-correctness': [
        'fix_makefile_bare_pytest', 'fix_makefile_bare_vitest',
        'fix_makefile_pytest_in_non_python', 'fix_package_json_bare_jest',
        'fix_makefile_npm_test_jest', 'fix_makefile_binary_name',
        'fix_jest_no_tests_found', 'fix_jest_config_js',
        'fix_vitest_watch_mode', 'fix_vitest_globals'],
    'brace-paren-balance': [
        'fix_json_unclosed_brackets', 'fix_csharp_missing_braces',
        'fix_js_extra_closing_brace', 'fix_rust_unbalanced_braces',
        'fix_missing_close_paren'],
    'syntax-artifact': [
        'fix_tool_call_artifacts', 'fix_literal_newlines',
        'fix_makefile_literal_tab_escape', 'fix_makefile_literal_newline_escape',
        'fix_makefile_escaped_dollar', 'fix_makefile_backslash_artifact',
        'fix_csharp_verbatim_string_escape', 'fix_csharp_keyword_prefix_artifacts',
        'fix_multiline_single_quote', 'fix_python_decorator_colon'],
    'build-rule-structure': [
        'fix_makefile_space_indent', 'fix_orphan_top_level_commands',
        'fix_no_targets', 'fix_inline_recipe', 'fix_nested_targets',
        'fix_binary_target_runs_itself', 'fix_makefile_missing_compile_rule',
        'fix_makefile_double_colon_target', 'fix_makefile_recipe_is_prerequisite_list',
        'fix_missing_venv_rule', 'fix_makefile_wrong_c_compiler',
        'fix_makefile_sdl2_config_typo', 'fix_config_tool_redundant_flag',
        'fix_makefile_pip_no_venv', 'fix_python_venv_cmd'],
    'dependency-install': [
        'fix_missing_pip_packages', 'fix_vue_missing_package',
        'fix_vue_test_utils_import'],
    'code-structure': [
        'fix_python_method_indent', 'fix_python_missing_def',
        'fix_flask_post_missing_201', 'fix_flask_test_route_decorators',
        'fix_flask_init_db_import', 'fix_rust_println_missing_arg',
        'fix_rust_cargo_toml', 'fix_csharp_using_order', 'fix_js_env_data_file',
        'py_autofix'],
    'plan-spec': ['apply_plan_spec_reflexes'],
    'composite-chain': ['apply_makefile_reflexes', 'apply_go_reflexes'],
}
_ERROR_CLASS = {rid: cls for cls, ids in _CLASS_MEMBERS.items() for rid in ids}


@dataclass
class ReflexRecord:
    """One reflex's machine-readable metadata (docs/REFLEX_KB.md §3)."""
    id: str
    toolchain: str       # module it lives in (python, rust, makefile, …)
    error_class: str     # curated; 'uncategorized' if missing
    trigger: str         # scan · lint-out · test-out · project · plan (derived)
    scope: str           # file · project · multi-file (derived)


def _trigger_from_signature(params: list[str]) -> str:
    """Classify how a reflex decides to fire, from its argument names."""
    if any('lint' in p for p in params):
        return 'lint-out'
    if any(p in ('test_output', 'build_output', 'test_cmd') for p in params):
        return 'test-out'
    if any(p in ('goal', 'plan_file') for p in params):
        return 'plan'
    if any('project_dir' in p for p in params):
        return 'project'
    return 'scan'


def _scope_from_signature(params: list[str]) -> str:
    if any('project_dir' in p for p in params):
        return 'project'
    if any(p in ('file_path', 'f', 'req_path', 'plan_file') for p in params):
        return 'file'
    return 'project'


def discover() -> list[ReflexRecord]:
    """Introspect the reflex modules and build a record for every public
    ``fix_*`` / ``apply_*`` callable. Pure reflection — no metadata drift."""
    records: list[ReflexRecord] = []
    for mod_name in _MODULES:
        mod = getattr(reflexes, mod_name, None)
        if mod is None:
            continue
        for name in getattr(mod, '__all__', ()):
            if not (name.startswith('fix_') or name.startswith('apply_')):
                continue
            fn = getattr(mod, name, None)
            if not callable(fn):
                continue
            params = list(inspect.signature(fn).parameters)
            records.append(ReflexRecord(
                id=name,
                toolchain=mod_name,
                error_class=_ERROR_CLASS.get(name, 'uncategorized'),
                trigger=_trigger_from_signature(params),
                scope=_scope_from_signature(params),
            ))
    records.sort(key=lambda r: (r.error_class, r.toolchain, r.id))
    return records


def uncategorized() -> list[str]:
    """Reflex ids with no curated error_class — the completeness test fails if
    this is non-empty, forcing every new reflex to be classified."""
    return [r.id for r in discover() if r.error_class == 'uncategorized']


if __name__ == '__main__':
    for r in discover():
        print(f"{r.error_class:24} {r.toolchain:8} {r.trigger:9} {r.id}")
    missing = uncategorized()
    if missing:
        print(f"\nUNCATEGORIZED ({len(missing)}): {missing}")
