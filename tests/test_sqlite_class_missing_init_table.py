"""Tests for fix_sqlite_class_missing_init_table: adds _create_table() call to
__init__ when the method exists but is never called."""
import textwrap
from pathlib import Path
import pytest

from mu.reflexes.python import fix_sqlite_class_missing_init_table


@pytest.fixture()
def src(tmp_path):
    f = tmp_path / 'main.py'
    return f


def test_adds_create_table_call(src):
    src.write_text(textwrap.dedent("""\
        import sqlite3

        class TodoManager:
            def __init__(self):
                self.conn = sqlite3.connect(':memory:')
                self.cursor = self.conn.cursor()

            def _create_table(self):
                self.cursor.execute(
                    'CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT)'
                )
                self.conn.commit()

            def add(self, task):
                self.cursor.execute('INSERT INTO todos (task) VALUES (?)', (task,))
        """))

    result = fix_sqlite_class_missing_init_table(str(src))

    assert result is True
    content = src.read_text()
    assert 'self._create_table()' in content
    # Should be inside __init__
    init_idx = content.index('def __init__')
    call_idx = content.index('self._create_table()')
    create_method_idx = content.index('def _create_table')
    assert init_idx < call_idx < create_method_idx


def test_no_fire_when_already_called(src):
    src.write_text(textwrap.dedent("""\
        import sqlite3

        class TodoManager:
            def __init__(self):
                self.conn = sqlite3.connect(':memory:')
                self._create_table()

            def _create_table(self):
                self.conn.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY)')
        """))

    result = fix_sqlite_class_missing_init_table(str(src))
    assert result is False


def test_no_fire_on_test_file(tmp_path):
    f = tmp_path / 'test_main.py'
    f.write_text(textwrap.dedent("""\
        import sqlite3
        class T:
            def __init__(self):
                self.conn = sqlite3.connect(':memory:')
            def _create_table(self):
                self.conn.execute('CREATE TABLE IF NOT EXISTS t (x TEXT)')
        """))
    assert fix_sqlite_class_missing_init_table(str(f)) is False


def test_no_fire_without_create_table(src):
    src.write_text(textwrap.dedent("""\
        import sqlite3
        class TodoManager:
            def __init__(self):
                self.conn = sqlite3.connect(':memory:')
        """))
    assert fix_sqlite_class_missing_init_table(str(src)) is False


def test_idempotent(src):
    src.write_text(textwrap.dedent("""\
        import sqlite3

        class TodoManager:
            def __init__(self):
                self.conn = sqlite3.connect(':memory:')

            def setup(self):
                self.conn.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY)')
        """))

    fix_sqlite_class_missing_init_table(str(src))
    first = src.read_text()
    fix_sqlite_class_missing_init_table(str(src))
    second = src.read_text()

    assert first == second
