import pytest
from todo import Todo
import sqlite3
import os

@pytest.fixture
def todo_db(tmp_path):
    db_path = tmp_path / "todo.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT)')
    conn.commit()
    yield Todo(str(db_path))
    conn.close()
    os.remove(db_path)


def test_add_todo(todo_db):
    todo_db.add("Buy milk")
    cursor = todo_db.conn.cursor()
    cursor.execute('SELECT * FROM todos')
    result = cursor.fetchone()
    assert result == (1, "Buy milk")


def test_list_todos(todo_db):
    todo_db.add("Buy milk")
    todo_db.add("Walk dog")
    todos = todo_db.list()
    assert todos == ["Buy milk", "Walk dog"]


def test_delete_todo(todo_db):
    todo_db.add("Buy milk")
    todo_db.add("Walk dog")
    todo_db.delete(1)
    todos = todo_db.list()
    assert todos == ["Walk dog"]


def test_delete_nonexistent_todo(todo_db):
    with pytest.raises(IndexError):
        todo_db.delete(999)