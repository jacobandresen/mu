import pytest
from todo import create_table, add_task, list_tasks, delete_task

def test_create_table():
    create_table()
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='todos' ''')
    assert c.fetchone() is not None
    conn.close()


def test_add_task():
    create_table()
    add_task('Buy groceries')
    tasks = list_tasks()
    assert len(tasks) == 1 and tasks[0][1] == 'Buy groceries'


def test_list_tasks():
    create_table()
    add_task('Buy groceries')
    add_task('Do laundry')
    tasks = list_tasks()
    assert len(tasks) == 2 and tasks[0][1] == 'Buy groceries' and tasks[1][1] == 'Do laundry'


def test_delete_task():
    create_table()
    add_task('Buy groceries')
    delete_task(1)
    tasks = list_tasks()
    assert len(tasks) == 0