"""fix_go_missing_pkg_imports: `go vet ./...` reports paths module-relative WITHOUT a
`./` prefix in multi-package projects (`vet: backend/tests/ping_test.go:…: undefined:
httptest`). The undef regex required `./`, so the reflex silently no-opped on every
staged Go project (p5-gin) — httptest/http/json were in the stdlib map but never applied.
"""
import shutil

import pytest

from mu.reflexes.go._common import _UNDEF_RE, _STDLIB_IMPORTS
from mu.reflexes.go import fix_go_missing_pkg_imports


def test_undef_regex_matches_module_relative_path():
    # The regression: no `./` prefix (go vet multi-package form).
    m = _UNDEF_RE.search('vet: backend/tests/ping_test.go:14:7: undefined: httptest')
    assert m and m.group(1) == 'backend/tests/ping_test.go' and m.group(2) == 'httptest'
    # Still matches the `./`-prefixed single-package form.
    m2 = _UNDEF_RE.search('./main.go:9:2: undefined: http')
    assert m2 and m2.group(1) == 'main.go' and m2.group(2) == 'http'
    assert _STDLIB_IMPORTS['httptest'] == 'net/http/httptest'


@pytest.mark.skipif(not shutil.which('go'), reason='go toolchain not installed')
def test_reflex_adds_stdlib_import_in_subpackage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'go.mod').write_text('module example.com/m\n\ngo 1.21\n')
    sub = tmp_path / 'backend' / 'tests'
    sub.mkdir(parents=True)
    # Uses httptest without importing it ⇒ `go vet` reports undefined: httptest.
    (sub / 'ping_test.go').write_text(
        'package tests\n\nfunc Use() { _ = httptest.NewRecorder() }\n')
    assert fix_go_missing_pkg_imports() is True
    assert '"net/http/httptest"' in (sub / 'ping_test.go').read_text()
