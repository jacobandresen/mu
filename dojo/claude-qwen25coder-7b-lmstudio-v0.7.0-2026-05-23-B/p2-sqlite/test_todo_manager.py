# test_todo_manager.py
import todo_manager
from db_handler import add_todo, list_todos, delete_todo


def test_add_todo():
    todo_manager.add_todo('Buy milk')
    todos = list_todos()
    assert len(todos) == 1 and todos[0][1] == 'Buy milk'

def test_list_todos():
    add_todo('Buy bread')
    todos = list_todos()
    assert len(todos) == 2 and todos[1][1] == 'Buy bread'

def test_delete_todo():
    delete_todo(1)
    todos = list_todos()
    assert len(todos) == 1