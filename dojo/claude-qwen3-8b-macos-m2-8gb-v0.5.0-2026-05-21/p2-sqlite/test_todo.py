from todo import TodoManager


def test_add_todo():
    manager = TodoManager(':memory:')
    manager.add_todo('Buy groceries')
    todos = manager.list_todos()
    assert len(todos) == 1
    assert todos[0]['task'] == 'Buy groceries'
    assert todos[0]['completed'] == 0


def test_list_todos():
    manager = TodoManager(':memory:')
    manager.add_todo('Task 1')
    manager.add_todo('Task 2')
    manager.conn.execute('UPDATE todos SET completed = 1 WHERE id = 1')
    
    # List all
    todos = manager.list_todos()
    assert len(todos) == 2
    assert todos[0]['task'] == 'Task 1'
    assert todos[0]['completed'] == 1
    assert todos[1]['task'] == 'Task 2'
    assert todos[1]['completed'] == 0

    # List completed
    todos = manager.list_todos(completed=True)
    assert len(todos) == 1
    assert todos[0]['task'] == 'Task 1'

    # List not completed
    todos = manager.list_todos(completed=False)
    assert len(todos) == 1
    assert todos[0]['task'] == 'Task 2'


def test_delete_todo():
    manager = TodoManager(':memory:')
    manager.add_todo('Task A')
    manager.add_todo('Task B')
    
    manager.delete_todo(1)
    todos = manager.list_todos()
    assert len(todos) == 1
    assert todos[0]['task'] == 'Task B'

    # Delete non-existent
    manager.delete_todo(999)
    todos = manager.list_todos()
    assert len(todos) == 1