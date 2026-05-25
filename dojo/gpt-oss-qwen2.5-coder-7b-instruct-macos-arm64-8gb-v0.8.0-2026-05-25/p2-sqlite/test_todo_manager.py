# test_todo_manager.py
from todo_manager import TodoManager

def test_add_task():
    manager = TodoManager()
    manager.add_task('Test Task')
    tasks = manager.list_tasks()
    assert len(tasks) == 1
    assert tasks[0][1] == 'Test Task'
    manager.delete_task(tasks[0][0])

def test_list_tasks():
    manager = TodoManager()
    manager.add_task('Task 1')
    manager.add_task('Task 2')
    tasks = manager.list_tasks()
    assert len(tasks) == 2
    assert tasks[0][1] == 'Task 1'
    assert tasks[1][1] == 'Task 2'
    for task in tasks:
        manager.delete_task(task[0])

def test_delete_task():
    manager = TodoManager()
    manager.add_task('Delete Me')
    tasks = manager.list_tasks()
    assert len(tasks) == 1
    manager.delete_task(tasks[0][0])
    tasks = manager.list_tasks()
    assert len(tasks) == 0