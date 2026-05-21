import sqlite3
import os

DB_NAME = "todos.db"

def connect_db():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        return conn
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return None

def initialize_db():
    """Initializes the database by creating the todos table if it does not exist."""
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            completed INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_todo(task: str):
    """Adds a new todo item to the database."""
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task, completed) VALUES (?, ?)", (task, 0))
    conn.commit()
    conn.close()

def list_todos():
    """Retrieves all todo items from the database."""
    conn = connect_db()
    if conn is None:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, completed FROM todos ORDER BY id")
    todos = cursor.fetchall()
    conn.close()
    return todos

def delete_todo(todo_id: int):
    """Deletes a todo item by its ID."""
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def mark_todo_completed(todo_id: int):
    """Marks a todo item as completed by setting the completed status to 1."""
    conn = connect_db()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Example usage for testing purposes
    initialize_db()
    print("Database initialized.")
    
    add_todo("Learn Python")
    add_todo("Write tests")
    
    print("\n--- Todos after adding ---")
    print(list_todos())
    
    # Mark the first one as completed
    # We need to find the ID first, which is not directly exposed by list_todos() in this simple setup.
    # For this example, we rely on the test file to handle the flow.
    
    # To demonstrate the functions work:
    # We would need to modify list_todos to return IDs or handle the flow differently for a runnable example.
    pass