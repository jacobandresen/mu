import os
import sqlite3

# Initialize the database
def init_database():
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

# Test the todo list manager
def test_todo():
    init_database()
    # Check if the database file exists
    assert os.path.exists("todo.db")
    # Check if the todos table exists
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todos'")
    result = cursor.fetchone()
    conn.close()
    assert result is not None

    # Add a todo
    add_todo("Learn Python")
    # List todos
    todos = list_todos()
    assert todos[0] == "Learn Python"

    # Delete a todo
    delete_todo("Learn Python")
    # List todos after deletion
    todos = list_todos()
    assert len(todos) == 0

    # Try to delete a non-existent todo
    delete_todo("Non-existent todo")
    # List todos after deletion
    todos = list_todos()
    assert len(todos) == 0

    # Add a todo with a different item
    add_todo("Test item")
    # List todos
    todos = list_todos()
    assert todos[0] == "Test item"

    # Delete the test item
    delete_todo("Test item")
    # List todos after deletion
    todos = list_todos()
    assert len(todos) == 0

if __name__ == "__main__":
    test_todo()