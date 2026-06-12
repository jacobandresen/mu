"""Regression: fix_python_missing_stdlib_imports must not re-add names that
are already bound by a different import form.

2026-06-12 collection run: files starting with `from flask import Flask,
request, jsonify` got all three imports appended again (the old check tested
the *key* as a module name, `^from Flask`), tripping flake8 F811 redefinition
at the lint gate — 6 stalled sessions in one 3h run.
"""

from pathlib import Path

from mu.reflexes.python import fix_python_missing_stdlib_imports

FLASK_APP = """from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)


@app.route('/todos', methods=['POST'])
def add():
    data = request.get_json()
    conn = sqlite3.connect('todos.db')
    return jsonify(data), 201
"""


def test_combined_from_import_not_duplicated(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text(FLASK_APP)
    changed = fix_python_missing_stdlib_imports(str(f))
    text = f.read_text()
    assert not changed, f'reflex re-added imports:\n{text}'
    assert text == FLASK_APP


def test_alias_import_counts_as_bound(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text("import simplejson as json\n\nprint(json.dumps({}))\n")
    assert not fix_python_missing_stdlib_imports(str(f))
    assert 'import json\n' not in f.read_text().replace('simplejson as json', '')


def test_genuinely_missing_import_still_added(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text("conn = sqlite3.connect(':memory:')\n")
    assert fix_python_missing_stdlib_imports(str(f))
    assert 'import sqlite3' in f.read_text()


def test_idempotent_after_adding(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text("conn = sqlite3.connect(':memory:')\n")
    assert fix_python_missing_stdlib_imports(str(f))
    once = f.read_text()
    assert not fix_python_missing_stdlib_imports(str(f))
    assert f.read_text() == once
