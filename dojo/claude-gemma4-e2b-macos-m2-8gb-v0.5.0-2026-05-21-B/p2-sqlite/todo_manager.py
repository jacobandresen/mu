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

def add_todo(task):
    """Adds a new todo item to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task, completed) VALUES (?, ?)", (task, 0))
    conn.commit()
    conn.close()

def list_todos():
    """Retrieves all todos from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, completed FROM todos")
    todos = cursor.fetchall()
    conn.close()
    return todos

def delete_todo(todo_id):
    """Deletes a todo item by its ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    initialize_db()
    print("Todo Manager initialized.")
    
    # Example usage
    add_todo("Buy groceries")
    add_todo("Write code")
    
    print("\n--- Current Todos ---")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Task: {todo[1]}, Completed: {todo[2]}")
        
    # Example deletion (assuming the first added item is the one to delete for demonstration)
    if list_todos():
        first_id = list_todos()[0][0]
        delete_todo(first_id)
        print(f"\nDeleted todo with ID: {first_id}")
        
    print("\n--- Todos after deletion ---")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Task: {todo[1]}, Completed: {todo[2]}")