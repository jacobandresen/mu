import sqlite3
import os

def connect_db():
    """Connect to the SQLite database and return a connection object."""
    db_path = "todo.db"
    if not os.path.exists(db_path):
        # Create the database file if it doesn't exist
        conn = sqlite3.connect(db_path)
        conn.close()
    return sqlite3.connect(db_path)

def add_todo(item):
    """Add a new todo item to the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (item) VALUES (?)", (item,))
    conn.commit()
    conn.close()
    print(f"Added todo: {item}")

def list_todos():
    """List all todo items from the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT item FROM todos ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("No todos to show.")
    else:
        for row in rows:
            print(f"- {row[0]}")

def delete_todo(item):
    """Delete a todo item from the database by its text."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE item = ?", (item,))
    if cursor.rowcount == 0:
        print(f"Todo '{item}' not found.")
    else:
        conn.commit()
        print(f"Deleted todo: {item}")
    conn.close()

def init_database():
    """Initialize the database with a todos table if it doesn't exist."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL
)
""")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_database()
    print("Todo list manager initialized.")

# Example usage:
# add_todo("Learn Python")
# list_todos()
# delete_todo("Learn Python")