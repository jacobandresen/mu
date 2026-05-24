from todo import init_db, add_task, list_tasks, delete_task
import sqlite3
def test_init_db():
    init_db()
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todos'")
    table_exists = c.fetchone()
    assert table_exists is not None
    conn.close()
def test_add_task():
    init_db()
    add_task('Buy groceries')
    tasks = list_tasks()
    assert len(tasks) == 1 and tasks[0][1] == 'Buy groceries'
def test_list_tasks():
    init_db()
    add_task('Buy groceries')
    tasks = list_tasks()
    assert len(tasks) == 1 and tasks[0][1] == 'Buy groceries'
def test_delete_task():
    init_db()
    add_task('Buy groceries')
    delete_task(1)
    tasks = list_tasks()
    assert len(tasks) == 0