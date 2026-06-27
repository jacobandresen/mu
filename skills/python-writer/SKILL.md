---
name: python-writer
description: Python code-generation and environment rules — imports, module naming, venv isolation, pytest version, stateless tests, Flask+SQLite patterns. Apply to any Python task that writes code, installs packages, or runs pytest.
---

## Imports
- Import every name you use; nothing is in scope unless imported. A test file imports the module under test on its first lines.
- Import name = filename stem: `todo.py` → `from todo import …`. Never guess `app`/`main`/`module`. A test using `app`/`db` must `from app import app, db`.
- Only real stdlib/installable modules — no `import self`, `import __name__`. Real newlines only, never a literal `\n` in file content.
- No setup behind `if __name__ == "__main__"`: DB connections and table creation must run at import time or in fixtures, so `import module` leaves something pytest can collect.

## Environment (Makefile / test command)
- Install into an isolated venv with `python3` (not `python`) — never `pip install` into the active interpreter:
  ```sh
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt pytest
  PYTHONPATH=. .venv/bin/pytest
  ```
- **Always prefix pytest with `PYTHONPATH=.`** in the Makefile test recipe. Pytest walks up from the test file to find the nearest `pyproject.toml` or `setup.cfg` for rootdir, which may be a parent project's config — this breaks `import database`/`import main`/`import app` when tests live in a `tests/` subdirectory. Setting `PYTHONPATH=.` anchors module resolution to the project root regardless of rootdir.
- Require `pytest >= 8` on Python 3.12+ (older pytest crashes in its assertion rewriter — a tooling error no source edit fixes).
- Leave a dependency unpinned rather than guess a version; a wrong pin is worse than none. Flask ≥ 2.3 needs Werkzeug ≥ 2.3.

## Stateless tests
- Each test starts from clean state: `tmp_path`, an in-memory DB (`sqlite3.connect(":memory:")`), or a fixture that resets state. Never assert absolute row counts against a store other tests also write.

## Flask + SQLite (no ORM)
- Use the `sqlite3` stdlib directly — no Flask-SQLAlchemy/SQLAlchemy/ORM in `requirements.txt`.
- Store ONE persistent connection on the `app` object, not per-request — per-request `:memory:` connections each get a fresh empty DB (POST writes conn A, GET opens empty conn B):
  ```python
  # app.py
  from flask import Flask, request, jsonify
  import sqlite3
  app = Flask(__name__)
  DATABASE = 'todos.db'

  def _db():
      conn = getattr(app, '_conn', None)
      if conn is None:
          app._conn = sqlite3.connect(app.config.get('DATABASE', DATABASE))
          app._conn.row_factory = sqlite3.Row
          app._conn.execute('CREATE TABLE IF NOT EXISTS todos '
                            '(id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
          app._conn.commit()
      return app._conn

  @app.route('/todos', methods=['POST'])
  def add_todo():
      task = request.get_json()['task']
      _db().execute('INSERT INTO todos (task) VALUES (?)', (task,))
      _db().commit()
      return jsonify({'task': task}), 201

  @app.route('/todos', methods=['GET'])
  def get_todos():
      return jsonify([dict(r) for r in _db().execute('SELECT * FROM todos').fetchall()])
  ```
- Flask tests use the test client — never call route functions directly. Reset `app._conn = None` for a fresh in-memory DB per test:
  ```python
  # test_app.py
  import pytest
  from app import app

  @pytest.fixture
  def client():
      app.config['TESTING'] = True
      app.config['DATABASE'] = ':memory:'
      app._conn = None
      with app.test_client() as c:
          yield c
      app._conn = None

  def test_add_and_get(client):
      assert client.post('/todos', json={'task': 'buy milk'}).status_code == 201
      r = client.get('/todos')
      assert r.status_code == 200
      assert any(t['task'] == 'buy milk' for t in r.get_json())
  ```
