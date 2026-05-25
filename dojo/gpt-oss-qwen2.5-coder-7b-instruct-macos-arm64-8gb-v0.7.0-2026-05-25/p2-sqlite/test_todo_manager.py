from todo_manager import TodoManager

def test_add_task():
    tm = TodoManager()
    tm.add_task('Test Task')
    tasks = tm.list_tasks()
    assert len(tasks) == 1
    assert tasks[0][1] == 'Test Task'
    tm.delete_task(tasks[0][0])

def test_list_tasks_empty():
    tm = TodoManager()
    tasks = tm.list_tasks()
    assert len(tasks) == 0

def test_delete_task():
    tm = TodoManager()
    tm.add_task('Test Task')
    tasks = tm.list_tasks()
    task_id = tasks[0][0]
    tm.delete_task(task_id)
    tasks = tm.list_tasks()
    assert len(tasks) == 0