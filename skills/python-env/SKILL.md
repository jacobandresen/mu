---
name: python-env
description: Python environment and test-tooling rules — isolate venvs, match pytest to the interpreter, pin compatible deps, keep tests stateless. Apply to any Python task that installs packages or runs pytest.
---

Rules for any Python task that installs packages or runs tests. Each one exists
because ignoring it produces a real, repeated failure class.

## 1. Run tests in an isolated virtualenv — never `pip install` into the active env

`pip install -r requirements.txt && pytest` run against a shared interpreter
mutates that interpreter for every other project. A stale pin such as
`Flask==2.0.1` will downgrade an existing Flask 3.x and break it against the
installed Werkzeug 3.x:

```
ImportError: cannot import name 'url_quote' from 'werkzeug.urls'
```

Always sandbox the install + test in a throwaway venv that owns its own tools:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest   # tools live IN the sandbox
.venv/bin/pytest
```

A Makefile `test:` target for a pip-based project should create and use a local
`.venv`, not assume the caller's environment.

**Caveat — `--system-site-packages` does not inherit another venv's packages.**
A venv created from the *system* interpreter only sees the *system* site
(`/usr/lib/...`), not the tools installed in some other project venv. So either
install the full toolset (pytest + libs) into the sandbox, or build it from the
interpreter whose packages you actually want. Compilers and CLIs found via
`shutil.which` (clang, go, cargo, dotnet, ruff) are on `PATH` regardless and
need no reinstall.

## 2. The test runner must match the host Python

`pytest < 8` crashes on **Python 3.12+** inside its own assertion rewriter,
before collecting any test:

```
AttributeError: module 'ast' has no attribute 'Str'
```

`ast.Str` (and `ast.Num`, `ast.NameConstant`, …) were deprecated in 3.8 and
removed in 3.12. Require `pytest >= 8` on modern Python. This is a *tooling*
error, not a bug in the code under test — no source edit can fix it; upgrade the
tool. The same class applies to any test/lint tool pinned years behind the
interpreter.

## 3. Pin dependencies that are mutually compatible

Don't emit stale, individually-plausible pins. Flask, Werkzeug, and
Flask-SQLAlchemy move together:

- `Flask` ≥ 2.3 needs `Werkzeug` ≥ 2.3 (the `url_quote` removal boundary).
- `Flask-SQLAlchemy` 3.x needs `Flask` ≥ 2.2.5 **and** `SQLAlchemy` ≥ 2.0.
- Prefer leaving a dependency *unpinned* (latest compatible) over guessing a
  version. A wrong pin is worse than no pin.

## 4. Tests must be self-contained — no shared on-disk state

A SQLite-backed test that writes to a fixed file (`todos.db`) leaks rows between
test functions, so later assertions see accumulated state:

```
assert len(todos) == 0   # fails: 2 rows survive from earlier tests
```

Give each test a clean store: a `tmp_path` fixture, an in-memory DB
(`sqlite3.connect(":memory:")`), or a fixture that truncates tables in
setup/teardown. Never assert on absolute row counts across tests that share a
file.

## 5. Make modules import-safe

Code that pytest imports must not depend on `if __name__ == "__main__"` for
setup. Create tables / initialise resources at import time or inside fixtures,
so `import todo_manager` (done by the test collector) leaves a usable module.
