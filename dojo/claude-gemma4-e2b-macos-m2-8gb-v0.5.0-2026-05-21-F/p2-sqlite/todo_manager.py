import sqlite3

DB_NAME = "todos.db"

def setup_database():
    """Sets up the SQLite database and the todos table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            completed INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_todo(description):
    """Adds a new todo to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (description, completed) VALUES (?, ?)", (description, 0))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def list_todos():
    """Retrieves all todos from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, completed FROM todos ORDER BY id")
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

def mark_todo_completed(todo_id):
    """Marks a todo item as completed."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()
    print("Todo list manager initialized.")
    
    # Example usage
    id1 = add_todo("Buy groceries")
    id2 = add_todo("Finish project report")
    
    print(f"Added todo with ID: {id1}")
    print(f"Added todo with ID: {id2}")
    
    print("\nCurrent Todos:")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Description: {todo[1]}, Completed: {todo[2]}")
        
    mark_todo_completed(id1)
    
    print("\nTodos after marking ID 1 as completed:")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Description: {todo[1]}, Completed: {todo[2]}")

    delete_todo(id2)
    
    print("\nTodos after deleting ID 2:")
    for todo in list_todos():
        print(f"ID: {todo[0]}, Description: {todo[1]}, Completed: {todo[2]}")