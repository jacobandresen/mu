import sqlite3

DB_NAME = "todos.db"

def connect_db():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    return conn

def initialize_db():
    """Creates the todos table if it does not exist."""
    conn = connect_db()
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

initialize_db()

def add_todo(task):
    """Adds a new todo item to the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task, completed) VALUES (?, ?)", (task, 0))
    conn.commit()
    conn.close()

def list_todos():
    """Retrieves all todos from the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, completed FROM todos ORDER BY id DESC")
    todos = cursor.fetchall()
    conn.close()
    return todos

def delete_todo(todo_id):
    """Deletes a todo item by its ID."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def mark_todo_completed(todo_id):
    """Marks a todo item as completed by its ID."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def display_todos():
    """Prints all todos in a readable format."""
    todos = list_todos()
    if not todos:
        print("No todos found.")
        return

    print("\n--- To-Do List ---")
    for todo_id, task, completed in todos:
        status = "✅" if completed else "❌"
        print(f"{todo_id}. [{status}] {task}")
    print("------------------")

if __name__ == '__main__':
    # Initialize the database on startup
    initialize_db()

    print("Todo List Manager Initialized.")

    # Example usage
    print("\n--- Adding Todos ---")
    add_todo("Buy groceries")
    add_todo("Write code for todo app")
    add_todo("Test the database operations")

    display_todos()

    # Example: Mark a todo as completed (assuming the first added item is the one to mark)
    # In a real app, you'd prompt the user for the ID. Here we just demonstrate the function call.
    # For demonstration, let's find the ID of the first item added.
    all_todos = list_todos()
    if all_todos:
        first_id = all_todos[0][0]
        print(f"\nMarking todo ID {first_id} as completed...")
        mark_todo_completed(first_id)
        display_todos()

    # Example: Deleting a todo
    if all_todos:
        id_to_delete = all_todos[1][0] # Delete the second item
        print(f"\nDeleting todo ID {id_to_delete}...")
        delete_todo(id_to_delete)
        display_todos()