"""Tests for fix_sqlite_conn_scope: adds cursor = conn.cursor() at module level
when conn is top-level but cursor is missing and a test imports cursor."""

import tempfile
from pathlib import Path

from mu.reflexes.python import fix_sqlite_conn_scope


def _setup(tmp: Path, main_src: str, test_src: str) -> tuple[Path, Path]:
    main_f = tmp / 'main.py'
    test_f = tmp / 'test_main.py'
    main_f.write_text(main_src)
    test_f.write_text(test_src)
    return main_f, test_f


def test_adds_cursor_when_missing():
    with tempfile.TemporaryDirectory() as td:
        main_f, _ = _setup(
            Path(td),
            "import sqlite3\nconn = sqlite3.connect(':memory:')\n\ndef add(task): pass\n",
            "from main import cursor\n\ndef test_x(): assert cursor is not None\n",
        )
        assert fix_sqlite_conn_scope(str(main_f))
        result = main_f.read_text()
        assert 'cursor = conn.cursor()' in result
        # cursor must appear after conn line
        conn_pos = result.index('conn = sqlite3')
        cursor_pos = result.index('cursor = conn.cursor()')
        assert cursor_pos > conn_pos


def test_no_fire_when_cursor_already_present():
    with tempfile.TemporaryDirectory() as td:
        main_f, _ = _setup(
            Path(td),
            "import sqlite3\nconn = sqlite3.connect(':memory:')\ncursor = conn.cursor()\n",
            "from main import cursor\n",
        )
        assert not fix_sqlite_conn_scope(str(main_f))


def test_no_fire_without_test_importing_cursor():
    with tempfile.TemporaryDirectory() as td:
        main_f, _ = _setup(
            Path(td),
            "import sqlite3\nconn = sqlite3.connect(':memory:')\n",
            "from main import add\n",
        )
        assert not fix_sqlite_conn_scope(str(main_f))


def test_no_fire_when_conn_not_module_level():
    """conn inside a class __init__ — indented, should not match."""
    with tempfile.TemporaryDirectory() as td:
        main_f, _ = _setup(
            Path(td),
            "import sqlite3\nclass DB:\n    def __init__(self):\n        self.conn = sqlite3.connect(':memory:')\n",
            "from main import cursor\n",
        )
        assert not fix_sqlite_conn_scope(str(main_f))


def test_no_fire_on_test_file_itself():
    with tempfile.TemporaryDirectory() as td:
        test_f = Path(td) / 'test_main.py'
        test_f.write_text("import sqlite3\nconn = sqlite3.connect(':memory:')\nfrom main import cursor\n")
        assert not fix_sqlite_conn_scope(str(test_f))


def test_idempotent():
    with tempfile.TemporaryDirectory() as td:
        main_f, _ = _setup(
            Path(td),
            "import sqlite3\nconn = sqlite3.connect(':memory:')\n",
            "from main import cursor\n",
        )
        fix_sqlite_conn_scope(str(main_f))
        first = main_f.read_text()
        fix_sqlite_conn_scope(str(main_f))
        assert main_f.read_text() == first
