import sqlite3
import sys


class TodoManager:
    def __init__(self, db_path='todos.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    completed BOOLEAN DEFAULT FALSE
                )
            """
            )
            conn.commit()

    def add_todo(self, task):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO todos (task) VALUES (?)', (task,))
            conn.commit()
            print(f"Added todo: {task}")

    def list_todos(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM todos')
            todos = cursor.fetchall()
            if not todos:
                print("No todos found.")
                return
            print("Todos:")
            for todo in todos:
                print(f"{todo[0]}. {todo[1]} - {'Completed' if todo[2] else 'Pending'}")

    def delete_todo(self, todo_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
            conn.commit()
            print(f"Deleted todo with ID: {todo_id}")


if __name__ == '__main__':
    manager = TodoManager()
    if len(sys.argv) < 2:
        print("Usage: python todo_manager.py <command> [arguments]")
        print("Commands: add, list, delete")
        sys.exit(1)

    command = sys.argv[1]
    if command == 'add':
        if len(sys.argv) < 3:
            print("Usage: python todo_manager.py add <task>")
            sys.exit(1)
        task = sys.argv[2]
        manager.add_todo(task)
    elif command == 'list':
        manager.list_todos()
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("Usage: python todo_manager.py delete <todo_id>")
            sys.exit(1)
        todo_id = int(sys.argv[2])
        manager.delete_todo(todo_id)
    else:
        print("Invalid command. Usage: add, list, delete")
        sys.exit(1)