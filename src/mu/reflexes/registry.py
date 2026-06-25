"""Reflex catalog: machine-readable metadata for every reflex.

The reflex functions live in the per-language modules; this module gives each a
*record* — the schema from docs/REFLEX_KB.md §3 — so the reflex layer becomes
queryable (which exist, what class, what trigger) and analysable (the SQLite KB
in reflexdb.py joins firings against these records).

**Traceability.** The catalog below references the reflex **functions directly**,
not by name string — ``rust.fix_rust_duplicate_use``, not
``'fix_rust_duplicate_use'``. So the link from a catalog entry to its
implementation is a real symbol reference: jump-to-definition works, "find
usages" connects the two, and a renamed or deleted reflex breaks the import
*immediately* instead of silently going stale. Grouping the references by
``error_class`` keeps the cross-toolchain families visible at a glance.

Most other attributes are derived from the function itself so they never drift:
``id`` from ``__name__``, ``toolchain`` from ``__module__``, ``trigger``/``scope``
from the signature.
"""

import inspect
from dataclasses import dataclass
from pathlib import Path

from mu.reflexes import (core, csharp, go, javascript, makefile, plan_reflexes,
                         python, rust)

# ── controlled vocabularies (exported for tests) ──────────────────────────────
PHASE_VOCAB: frozenset[str] = frozenset({'plan', 'write', 'repair'})
RISK_VOCAB:  frozenset[str] = frozenset({'low', 'medium', 'high'})

# trigger → execution phase (static, derivable from the function's signature class)
_PHASE_MAP: dict[str, str] = {
    'scan':     'write',
    'lint-out': 'write',
    'project':  'write',
    'test-out': 'repair',
    'plan':     'plan',
}


def _load_idempotent_ids() -> frozenset[str]:
    """IDs confirmed idempotent by tests/test_reflex_idempotency.py double-apply."""
    p = Path(__file__).with_name('idempotent_ids.txt')
    try:
        return frozenset(ln.strip() for ln in p.read_text().splitlines() if ln.strip())
    except OSError:
        return frozenset()


_IDEMPOTENT_IDS: frozenset[str] = _load_idempotent_ids()

# ── the catalog: error_class → the reflex functions in it ─────────────────────
# Direct function references (not strings) make the link to each implementation
# traceable and statically checked. Cross-toolchain families are obvious here:
# dependency-hygiene spans cargo/pip/npm; duplicate-declaration spans rust/js/cs.
_CATALOG: dict[str, list] = {
    'dependency-hygiene': [
        rust.fix_rust_cargo_bad_dependency, python.fix_requirements_stdlib_entries,
        python.fix_requirements_path_entries, javascript.fix_package_json_builtin_deps,
        makefile.fix_makefile_pip_install_empty],
    'duplicate-declaration': [
        rust.fix_rust_duplicate_use, javascript.fix_js_duplicate_require,
        javascript.fix_js_same_scope_redeclaration,
        csharp.fix_csharp_duplicate_classes,
        csharp.fix_csharp_cross_stage_duplicate_types, makefile.fix_duplicate_var],
    'type-visibility': [csharp.fix_csharp_public_signature_accessibility],
    'missing-symbol-import': [
        python.fix_python_undefined_imports, python.fix_python_missing_project_imports,
        python.fix_python_missing_stdlib_imports, javascript.fix_js_missing_requires,
        go.fix_go_missing_pkg_imports, csharp.fix_csharp_missing_using,
        rust.fix_rust_missing_trait_import, python.fix_test_import_module],
    'unused-import': [go.fix_go_unused_imports],
    'test-isolation': [
        python.fix_sqlite_test_isolation, python.fix_sqlite_conn_scope, python.fix_sqlite_memory_multi_connect,
        python.fix_sqlite_class_missing_init_table,
        javascript.fix_js_program_parse_guard,
        python.fix_missing_flask_client_fixture, javascript.fix_jest_fs_mock,
        python.fix_sqlite_missing_row_factory, python.fix_sqlite_path_unlink],
    'test-command-correctness': [
        makefile.fix_makefile_bare_pytest, makefile.fix_makefile_bare_vitest,
        makefile.fix_makefile_pytest_in_non_python, javascript.fix_package_json_bare_jest,
        makefile.fix_makefile_npm_test_jest, makefile.fix_makefile_binary_name,
        javascript.fix_jest_no_tests_found, javascript.fix_jest_esm, javascript.fix_jest_config_js,
        javascript.fix_vitest_watch_mode, javascript.fix_vitest_globals,
        makefile.fix_makefile_missing_test_target, makefile.fix_dotnet_test_cwd,
        csharp.fix_csharp_xunit_packages, csharp.fix_csharp_uninstalled_tfm,
        csharp.fix_csharp_package_tfm_mismatch,
        csharp.fix_csharp_test_program_conflict],
    'brace-paren-balance': [
        core.fix_json_unclosed_brackets, csharp.fix_csharp_missing_braces,
        csharp.fix_csharp_lambda_brace_confusion,
        javascript.fix_js_extra_closing_brace, javascript.fix_js_duplicate_const,
        rust.fix_rust_unbalanced_braces, python.fix_missing_close_paren],
    'syntax-artifact': [
        core.fix_tool_call_artifacts, core.fix_literal_newlines,
        makefile.fix_makefile_literal_tab_escape, makefile.fix_makefile_literal_newline_escape,
        makefile.fix_makefile_escaped_dollar, makefile.fix_makefile_backslash_artifact,
        csharp.fix_csharp_verbatim_string_escape, csharp.fix_csharp_keyword_prefix_artifacts,
        csharp.fix_csharp_consecutive_duplicate_signatures,
        python.fix_multiline_single_quote, python.fix_python_decorator_colon,
        python.fix_python_unindented_body,
        go.fix_go_trailing_dot],
    'build-rule-structure': [
        makefile.fix_makefile_space_indent, makefile.fix_orphan_top_level_commands,
        makefile.fix_no_targets, makefile.fix_inline_recipe, makefile.fix_nested_targets,
        makefile.fix_binary_target_runs_itself, makefile.fix_makefile_missing_compile_rule,
        makefile.fix_makefile_double_colon_target, makefile.fix_makefile_recipe_is_prerequisite_list,
        makefile.fix_makefile_executable_prerequisites,
        makefile.fix_missing_venv_rule, makefile.fix_makefile_wrong_c_compiler,
        makefile.fix_makefile_sdl2_config_typo, makefile.fix_config_tool_redundant_flag,
        makefile.fix_makefile_missing_libm,
        makefile.fix_makefile_pip_no_venv, makefile.fix_python_venv_cmd],
    'dependency-install': [
        python.fix_missing_pip_packages, javascript.fix_vue_missing_package,
        javascript.fix_vue_test_utils_import],
    'syntax-repair': [
        javascript.fix_js_const_reassignment,
        javascript.fix_js_dot_bracket_access,
        javascript.fix_vue_attr_quotes,
        javascript.fix_js_parent_to_sibling_import],
    'code-structure': [
        python.fix_python_method_indent, python.fix_python_missing_def,
        python.fix_flask_post_missing_201, python.fix_flask_test_route_decorators,
        python.fix_flask_init_db_import, rust.fix_rust_println_missing_arg,
        rust.fix_rust_cargo_toml, csharp.fix_csharp_using_order,
        javascript.fix_js_env_data_file, python.py_autofix],
    'plan-spec': [plan_reflexes.apply_plan_spec_reflexes],
    'composite-chain': [
        makefile.apply_makefile_reflexes, go.apply_go_reflexes,
        csharp.apply_csharp_write_reflexes, csharp.apply_csharp_repair_reflexes,
        javascript.apply_js_write_reflexes, javascript.apply_js_repair_reflexes,
        rust.apply_rust_source_reflexes,
    ],
}

# All language modules — scanned by the completeness check (§ below).
_MODULES = (core, python, rust, csharp, go, javascript, makefile, plan_reflexes)

# Per-reflex curated metadata: artifact, risk, evidence.
# Keyed by function reference (same traceability discipline as _CATALOG — no name strings).
# Omit a reflex to accept defaults: artifact=None, risk='low', evidence=''.
_ANNOTATIONS: dict = {
    # ── core ──────────────────────────────────────────────────────────────────
    core.fix_json_unclosed_brackets:           {'artifact': 'json'},
    # ── makefile ──────────────────────────────────────────────────────────────
    makefile.fix_makefile_space_indent:        {'artifact': 'Makefile'},
    makefile.fix_orphan_top_level_commands:    {'artifact': 'Makefile', 'risk': 'medium'},
    makefile.fix_no_targets:                   {'artifact': 'Makefile', 'risk': 'medium',
                                                'evidence': 'p5-c'},
    makefile.fix_inline_recipe:                {'artifact': 'Makefile', 'risk': 'medium'},
    makefile.fix_nested_targets:               {'artifact': 'Makefile', 'risk': 'medium'},
    makefile.fix_binary_target_runs_itself:    {'artifact': 'Makefile', 'risk': 'medium'},
    makefile.fix_makefile_pip_install_empty:   {'artifact': 'Makefile'},
    makefile.fix_duplicate_var:                {'artifact': 'Makefile'},
    makefile.apply_makefile_reflexes:          {'artifact': 'Makefile'},
    # ── rust ──────────────────────────────────────────────────────────────────
    rust.fix_rust_cargo_bad_dependency:        {'artifact': 'Cargo.toml',
                                                'evidence': 'p6-rust'},
    rust.fix_rust_duplicate_use:               {'artifact': 'rs'},
    rust.fix_rust_missing_trait_import:        {'artifact': 'rs'},
    rust.fix_rust_cargo_toml:                  {'artifact': 'Cargo.toml',
                                                'evidence': 'p6-rust'},
    # ── python ────────────────────────────────────────────────────────────────
    python.fix_missing_pip_packages:           {'artifact': 'requirements.txt',
                                                'evidence': 'p2-sqlite'},
    python.fix_sqlite_test_isolation:          {'artifact': 'py', 'evidence': 'p2-sqlite'},
    python.fix_sqlite_conn_scope:              {'artifact': 'py', 'evidence': 'p2-sqlite'},
    python.fix_sqlite_class_missing_init_table: {'artifact': 'py', 'evidence': 'p2-sqlite'},
    python.fix_sqlite_memory_multi_connect:    {'artifact': 'py', 'evidence': 'p2-sqlite'},
    python.fix_flask_init_db_import:           {'artifact': 'py', 'risk': 'medium',
                                                'evidence': 'p7-flask'},
    python.fix_flask_post_missing_201:         {'artifact': 'py', 'evidence': 'p7-flask'},
    python.fix_python_missing_def:             {'artifact': 'py', 'risk': 'medium'},
    python.fix_missing_flask_client_fixture:   {'artifact': 'py', 'evidence': 'p7-flask'},
    python.fix_test_import_module:             {'artifact': 'py', 'evidence': 'p2-sqlite'},
    # ── javascript ────────────────────────────────────────────────────────────
    javascript.fix_package_json_builtin_deps:  {'artifact': 'package.json'},
    javascript.fix_jest_fs_mock:               {'artifact': 'js', 'risk': 'medium',
                                                'evidence': 'p8-node'},
    javascript.fix_vue_missing_package:        {'artifact': 'package.json',
                                                'evidence': 'p9-vue'},
    javascript.fix_jest_esm:                   {'artifact': 'package.json'},
    javascript.fix_jest_config_js:             {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_js_duplicate_require:       {'artifact': 'js'},
    javascript.fix_js_missing_requires:        {'artifact': 'js'},
    # ── javascript (new) ─────────────────────────────────────────────────────
    javascript.fix_js_const_reassignment:      {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_js_duplicate_const:        {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_js_same_scope_redeclaration: {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_js_dot_bracket_access:     {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_js_program_parse_guard:    {'artifact': 'js', 'evidence': 'p8-node'},
    javascript.fix_vue_attr_quotes:            {'artifact': 'vue', 'evidence': 'p9-vue'},
    javascript.fix_js_parent_to_sibling_import: {'artifact': 'ts', 'evidence': 'p9-vue'},
    # ── makefile (new) ───────────────────────────────────────────────────────
    makefile.fix_makefile_missing_test_target: {'artifact': 'Makefile',
                                                'evidence': 'p7-flask'},
    makefile.fix_makefile_executable_prerequisites: {'artifact': 'Makefile',
                                                     'evidence': 'p7-flask'},
    makefile.fix_dotnet_test_cwd:              {'artifact': 'Makefile', 'risk': 'medium',
                                                'evidence': 'p10'},
    # ── csharp ────────────────────────────────────────────────────────────────
    csharp.fix_csharp_missing_braces:          {'artifact': 'cs', 'risk': 'medium'},
    csharp.fix_csharp_duplicate_classes:       {'artifact': 'cs'},
    csharp.fix_csharp_missing_using:           {'artifact': 'cs'},
    csharp.fix_csharp_xunit_packages:          {'artifact': 'csproj', 'evidence': 'p10'},
    csharp.fix_csharp_package_tfm_mismatch:    {'artifact': 'csproj', 'evidence': 'p4'},
    csharp.fix_csharp_uninstalled_tfm:         {'artifact': 'csproj', 'evidence': 'p10'},
    csharp.fix_csharp_test_program_conflict:   {'artifact': 'csproj', 'evidence': 'p4'},
    python.fix_python_unindented_body:         {'artifact': 'py', 'evidence': 'p7'},
    csharp.fix_csharp_consecutive_duplicate_signatures: {'artifact': 'cs', 'evidence': 'p4'},
    csharp.fix_csharp_lambda_brace_confusion:  {'artifact': 'cs', 'evidence': 'p10'},
    csharp.fix_csharp_cross_stage_duplicate_types: {'artifact': 'cs', 'evidence': 'p10', 'risk': 'medium'},
    csharp.fix_csharp_public_signature_accessibility: {'artifact': 'cs', 'evidence': 'p10', 'risk': 'medium'},
    # ── go ────────────────────────────────────────────────────────────────────
    go.fix_go_missing_pkg_imports:             {'artifact': 'go'},
    go.fix_go_unused_imports:                  {'artifact': 'go'},
    go.fix_go_trailing_dot:                    {'artifact': 'go', 'evidence': 'p5-gin'},
    go.apply_go_reflexes:                      {'artifact': 'go'},
    # ── composite chains (iter 4) ─────────────────────────────────────────────
    csharp.apply_csharp_write_reflexes:        {'artifact': 'cs'},
    csharp.apply_csharp_repair_reflexes:       {'artifact': 'cs'},
    javascript.apply_js_write_reflexes:        {'artifact': 'js'},
    javascript.apply_js_repair_reflexes:       {'artifact': 'js'},
    rust.apply_rust_source_reflexes:           {'artifact': 'rs'},
}


@dataclass
class ReflexRecord:
    """One reflex's machine-readable metadata (docs/REFLEX_KB.md §3)."""
    id: str
    toolchain: str         # module it lives in (python, rust, makefile, …)
    error_class: str       # from the catalog above
    trigger: str           # scan · lint-out · test-out · project · plan (derived)
    scope: str             # file · project (derived)
    summary: str           # one-line docstring (the schema is the documentation, §2)
    artifact: str | None   # curated: file type this reflex targets (None = unspecified)
    phase: str             # derived from trigger: write · repair · plan
    idempotent: bool | None  # measured by test_reflex_idempotency; None = untested
    risk: str              # curated: low · medium · high
    evidence: str          # curated: dojo problem id(s) that motivated this reflex


def _summary(fn) -> str:
    """The reflex's one-line description: the first non-empty docstring line,
    whitespace-collapsed and clipped. '' when the function has no docstring."""
    doc = inspect.getdoc(fn) or ''
    line = next((ln.strip() for ln in doc.splitlines() if ln.strip()), '')
    return ' '.join(line.split())[:120]


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


def _record(fn, error_class: str) -> ReflexRecord:
    """Build a record straight from the function object — no name strings."""
    params = list(inspect.signature(fn).parameters)
    scope = 'project' if any('project_dir' in p for p in params) else 'file'
    trigger = _trigger_from_signature(params)
    ann = _ANNOTATIONS.get(fn, {})
    is_scan_file = (trigger == 'scan' and scope == 'file')
    return ReflexRecord(
        id=fn.__name__,
        # Toolchain = the package under mu.reflexes, whether the reflex lives in
        # a single module (mu.reflexes.core) or a per-reflex file inside a
        # toolchain package (mu.reflexes.go.fix_go_trailing_dot -> "go").
        toolchain=fn.__module__.split('mu.reflexes.', 1)[-1].split('.', 1)[0],
        error_class=error_class,
        trigger=trigger,
        scope=scope,
        summary=_summary(fn),
        artifact=ann.get('artifact', None),
        phase=_PHASE_MAP[trigger],
        idempotent=(fn.__name__ in _IDEMPOTENT_IDS) if is_scan_file else None,
        risk=ann.get('risk', 'low'),
        evidence=ann.get('evidence', ''),
    )


def discover() -> list[ReflexRecord]:
    """Every cataloged reflex, as a record. Built from the function references in
    ``_CATALOG`` so the records cannot drift from the implementations."""
    records = [_record(fn, cls) for cls, fns in _CATALOG.items() for fn in fns]
    records.sort(key=lambda r: (r.error_class, r.toolchain, r.id))
    return records


def unregistered() -> list[str]:
    """Public ``fix_*`` / ``apply_*`` reflexes that exist in the modules but are
    NOT in ``_CATALOG``. The completeness test fails if this is non-empty, so a
    new reflex must be added to the catalog (and thereby classified)."""
    cataloged = {fn.__name__ for fns in _CATALOG.values() for fn in fns}
    found = set()
    for mod in _MODULES:
        for name in getattr(mod, '__all__', ()):
            if name.startswith(('fix_', 'apply_')):
                found.add(name)
    return sorted(found - cataloged)


if __name__ == '__main__':
    for r in discover():
        print(f"{r.error_class:24} {r.toolchain:8} {r.trigger:9} {r.id}")
    missing = unregistered()
    if missing:
        print(f"\nUNREGISTERED ({len(missing)}) — add to _CATALOG: {missing}")
