def test_list_todos():
    manager = TodoManager()
    manager.add_todo("Task 1")
    manager.add,add_todo("Task 2")

    todos = manager.list_todos()
    assert len(todos) == 2


def test_delete_todo():
    manager = TodoManager()
    manager.add_todo("Task to delete")
    todo_id = manager.get_last_inserted_id()
    manager.delete_todo(todo_id)

    with sqlite3.connect(manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM todos")
        todos = cursor.fetchall()
        assert len(todos) == 0