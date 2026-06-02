---
name: python-writer
description: Python code-generation rules — import discipline and module naming. Apply to any Python writing task alongside python-env.
---

- **Import every name you use.** Test files must import the module under test on their first lines. Nothing is in scope unless imported.
- **No synthetic imports.** Never write `import self`, `import __name__`, or any identifier that is not a real stdlib or installable module.
- **Import name = filename.** If the file is `todo.py`, the import is `from todo import …`. Match the stem exactly — never guess `app`, `main`, or `module`.
- **Test files must import every name they use from the implementation.** If `test_app.py` uses `app`, `db`, `client`, or any object defined in `app.py`, it must explicitly import it: `from app import app, db`. Never rely on implicit scope.
- **No `if __name__ == "__main__"` guards around setup.** DB connections, table creation, and app objects used by tests must execute at import time so pytest can collect without hitting the guard.
- **Real newlines only.** Never write `\n` as a literal escape sequence inside file content — use actual line breaks. A file written as one long string with `\n` characters will fail to parse.
- **Flask + SQLite: use the `sqlite3` stdlib module directly — no ORM.** Do NOT use Flask-SQLAlchemy, SQLAlchemy, or any other ORM. ORMs add complexity and require extra pip packages. Use `import sqlite3` and `sqlite3.connect(...)` directly. The `sqlite3` module is built into Python and requires no install. Never add `flask-sqlalchemy`, `flask_sqlalchemy`, `sqlalchemy`, or `SQLAlchemy` to `requirements.txt` for a plain Flask+SQLite task.
- **Flask + SQLite: store one persistent connection on the `app` object, not per-request.** Do NOT create a new `sqlite3.connect(...)` inside each route handler or each `TodoManager()` call. Per-request connections to `:memory:` create a fresh empty database for every request — POST inserts to connection A, GET opens connection B (empty), finds nothing. Instead, store the connection on the Flask app object itself:
  ```python
  # app.py — one persistent connection, no TodoManager class needed
  from flask import Flask, request, jsonify
  import sqlite3

  app = Flask(__name__)
  DATABASE = 'todos.db'

  def _db():
      conn = getattr(app, '_conn', None)
      if conn is None:
          app._conn = sqlite3.connect(app.config.get('DATABASE', DATABASE))
          app._conn.row_factory = sqlite3.Row
          app._conn.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
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
      rows = _db().execute('SELECT * FROM todos').fetchall()
      return jsonify([dict(r) for r in rows])
  ```
- **Flask REST API tests MUST use Flask's test client — never call ORM methods directly.** Tests that call `todo_manager.add_todo(...)` and assert `response.status_code == 201` are wrong — `add_todo` returns None, not an HTTP response. The correct test pattern resets `app._conn = None` to force a fresh in-memory database per test:
  ```python
  # test_app.py — no init_db import needed
  import pytest
  from app import app

  @pytest.fixture
  def client():
      app.config['TESTING'] = True
      app.config['DATABASE'] = ':memory:'
      app._conn = None  # force fresh in-memory db
      with app.test_client() as c:
          yield c
      app._conn = None  # cleanup

  def test_add_todo(client):
      r = client.post('/todos', json={'task': 'buy milk'})
      assert r.status_code == 201

  def test_get_todos(client):
      client.post('/todos', json={'task': 'buy milk'})
      r = client.get('/todos')
      assert r.status_code == 200
      assert any(t['task'] == 'buy milk' for t in r.get_json())
  ```
