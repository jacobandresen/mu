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
    # Initialize the database on startup
    initialize_db()

    print("--- To-Do List Manager ---")

    while True:
        print("\nOptions:")
        print("1. Add todo")
        print("2. List todos")
        print("3. Mark todo as completed")
        print("4. Delete todo")
        print("5. Exit")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            task = input("Enter the task: ")
            if task:
                add_todo(task)
                print(f"Task '{task}' added.")
            else:
                print("Task cannot be empty.")
        elif choice == '2':
            display_todos()
        elif choice == '3':
            list_items = list_todos()
            if not list_items:
                print("No tasks to mark as completed.")
                continue
            print("\nSelect a task to mark as completed:")
            for todo_id, task, completed in list_items:
                status = "✅" if completed else "❌"
                print(f"{todo_id}. [{status}] {task}")

            try:
                selected_id = int(input("Enter the ID of the task to mark as completed: "))
                mark_todo_completed(selected_id)
                print(f"Task ID {selected_id} marked as completed.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        elif choice == '4':
            list_items = list_todos()
            if not list_items:
                print("No tasks to delete.")
                continue
            print("\nSelect a task to delete:")
            for todo_id, task, completed in list_items:
                status = "✅" if completed else "❌"
                print(f"{todo_id}. [{status}] {task}")

            try:
                selected_id = int(input("Enter the ID of the task to delete: "))
                delete_todo(selected_id)
                print(f"Task ID {selected_id} deleted.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        elif choice == '5':
            print("Exiting To-Do List Manager. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")