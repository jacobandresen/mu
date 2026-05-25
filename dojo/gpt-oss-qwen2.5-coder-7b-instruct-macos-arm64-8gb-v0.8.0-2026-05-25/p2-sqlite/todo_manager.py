# todo_manager.py
import sqlite3

class TodoManager:
    def __init__(self, db_path='todos.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def add_task(self, task):
        self.cursor.execute('INSERT INTO todos (task) VALUES (?)', (task,))
        self.conn.commit()

    def list_tasks(self):
        self.cursor.execute('SELECT * FROM todos')
        return self.cursor.fetchall()

    def delete_task(self, task_id):
        self.cursor.execute('DELETE FROM todos WHERE id = ?', (task_id,))
        self.conn.commit()

if __name__ == '__main__':
    manager = TodoManager()
    while True:
        print("1. Add Task")
        print("2. List Tasks")
        print("3. Delete Task")
        print("4. Exit")
        choice = input('Enter your choice: ')

        if choice == '1':
            task = input('Enter task: ')
            manager.add_task(task)
        elif choice == '2':
            tasks = manager.list_tasks()
            for task in tasks:
                print(f"ID: {task[0]}, Task: {task[1]}")
        elif choice == '3':
            task_id = int(input('Enter task ID to delete: '))
            manager.delete_task(task_id)
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")