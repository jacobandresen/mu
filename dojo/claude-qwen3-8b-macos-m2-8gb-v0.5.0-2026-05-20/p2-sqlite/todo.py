import sqlite3


class TodoManager:
    def __init__(self, db_file='todos.db'):
        self.conn = sqlite3.connect(db_file)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    completed BOOLEAN DEFAULT 0
                )
            ''')

    def add_todo(self, task):
        with self.conn:
            self.conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))

    def list_todos(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM todos')
        return cursor.fetchall()

    def delete_todo(self, todo_id):
        with self.conn:
            self.conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))


if __name__ == '__main__':
    manager = TodoManager()
    manager.add_todo('Buy groceries')
    manager.add_todo('Walk the dog')
    print('Todos:', manager.list_todos())
    manager.delete_todo(1)
    print('Todos after deletion:', manager.list_todos())