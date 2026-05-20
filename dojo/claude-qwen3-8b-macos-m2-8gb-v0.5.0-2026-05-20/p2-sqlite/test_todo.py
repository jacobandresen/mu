import pytest
from todo import TodoManager


def test_add_todo():
    manager = TodoManager(':memory:')
    manager.add_todo('Buy groceries')
    todos = manager.list_todos()
    assert len(todos) == 1
    assert todos[0][1] == 'Buy groceries'


def test_list_todos():
    manager = TodoManager(':memory:')
    manager.add_todo('Task 1')
    manager.add_todo('Task 2')
    todos = manager.list_todos()
    assert len(todos) == 2
    assert todos[0][1] == 'Task 1'
    assert todos[1][1] == 'Task 2'


def test_delete_todo():
    manager = TodoManager(':memory:')
    manager.add_todo('Task 1')
    manager.delete_todo(1)
    todos = manager.list_todos()
    assert len(todos) == 0


def test_delete_nonexistent_todo():
    manager = TodoManager(':memory:')
    manager.delete_todo(999)
    todos = manager.list_todos()
    assert len(todos) == 0


# Run tests when file is executed
if __name__ == '__main__':
    pytest.main()