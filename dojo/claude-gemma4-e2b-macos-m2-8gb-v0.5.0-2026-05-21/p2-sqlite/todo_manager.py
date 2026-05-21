import sqlite3
import os

DB_NAME = "todos.db"

def initialize_db():
    """Initializes the SQLite database and creates the todos table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            completed BOOLEAN NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_todo(task: str):
    """Adds a new todo item to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task, completed) VALUES (?, ?)", (task, 0))
    conn.commit()
    conn.close()

def list_todos():
    """Retrieves all todo items from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, completed FROM todos")
    todos = cursor.fetchall()
    conn.close()
    return todos

def delete_todo(todo_id: int):
    """Deletes a todo item by its ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    initialize_db()
    print("Todo list manager initialized.")
    
    # Example usage
    add_todo("Buy groceries")
    add_todo("Learn SQLite")
    
    print("\nCurrent Todos:")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Task: {todo[1]}, Completed: {todo[2]}")
        
    # Example deletion (assuming ID 1 is the first added)
    # Note: The test will handle the actual deletion logic based on IDs generated.
    # delete_todo(1)
    
    print("\nTodos after potential deletion:")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Task: {todo[1]}, Completed: {todo[2]}")