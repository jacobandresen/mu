"""Cross-stage type-ownership guard (plan S2 / Step 0.3).

The staged writer often re-declares a shared type (``Post``, the EF ``DbContext``)
in a second project — typically the xUnit test project re-defines what the backend
already owns — and the compiler rejects it with **CS0101** (duplicate type in the
global namespace). p10's dominant error (×14).

Unlike :func:`fix_csharp_duplicate_classes` (per-file, same-directory siblings),
this is **project-wide and ownership-aware**: it scans every ``.cs`` under the
project, assigns each type a single owner — preferring a **non-test** file (the
backend), since a test project references shared types and must never own them —
and removes the duplicate block from every other file. General to any multi-project
.NET layout; a uniquely-named type is never touched.
"""
from pathlib import Path

from mu.reflexes.core import noted  # noqa: F401

from ._common import (_TYPE_DECL_RE, _cs_source_files, _is_test_path,
                      _strip_type_block)


def fix_csharp_cross_stage_duplicate_types(project_dir: str = '.') -> bool:
    """Keep one definition of each type (the backend-owned one) and delete the
    cross-project duplicates. Returns True if any file changed. Idempotent."""
    files = _cs_source_files(project_dir)
    if len(files) < 2:
        return False
    # Ownership: non-test files first, then by path — so the backend definition
    # wins even when the test dir (e.g. ``backend.Tests/``) sorts before it. Judge
    # test-ness on the path *relative to the project* so a project root that happens
    # to contain "test" (e.g. a temp dir) doesn't taint every file.
    root = Path(project_dir)

    def _rel_is_test(f: Path) -> bool:
        try:
            return _is_test_path(f.relative_to(root))
        except ValueError:
            return _is_test_path(f)

    for_owner = sorted(files, key=lambda f: (_rel_is_test(f), str(f)))
    owners: dict[str, Path] = {}
    for f in for_owner:
        try:
            src = f.read_text(errors='ignore')
        except OSError:
            continue
        for name in _TYPE_DECL_RE.findall(src):
            owners.setdefault(name, f)

    changed = False
    for f in files:
        try:
            text = f.read_text(errors='ignore')
        except OSError:
            continue
        file_changed = False
        for name in sorted(set(_TYPE_DECL_RE.findall(text))):
            if owners.get(name) is not None and owners[name] != f:
                text, removed = _strip_type_block(text, name)
                file_changed = file_changed or removed
        if file_changed:
            f.write_text(text)
            changed = True
            print(f"==> [mu-agent] Reflex: removed cross-stage duplicate type(s) "
                  f"from {f}")
    return changed
