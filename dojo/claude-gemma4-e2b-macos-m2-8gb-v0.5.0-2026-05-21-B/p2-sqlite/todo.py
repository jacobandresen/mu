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
    cursor.execute("SELECT id, task, completed FROM todos")
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
    # Initialize the database
    initialize_db()

    # Example usage
    print("--- Adding Todos ---")
    add_todo("Buy groceries")
    add_todo("Write code for todo app")
    add_todo("Test the functionality")

    print("\n--- Listing Todos ---")
    display_todos()

    # Example of marking a todo as completed (assuming the first added todo is the one to mark)
    if list_todos():
        first_todo_id = list_todos()[0][0]
        mark_todo_completed(first_todo_id)
        print(f"\nMarked todo ID {first_todo_id} as completed.")
        display_todos()

    # Example of deleting a todo
    if list_todos():
        todo_to_delete_id = list_todos()[1][0]
        delete_todo(todo_to_delete_id)
        print(f"\nDeleted todo ID {todo_to_delete_id}.")
        display_todos()