import sqlite3


class TodoManager:
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute(''
                'CREATE TABLE IF NOT EXISTS todos ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT,'
                'task TEXT NOT NULL,'
                'completed BOOLEAN DEFAULT 0)'
                '')

    def add_todo(self, task):
        with self.conn:
            self.conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))

    def list_todos(self, completed=None):
        query = 'SELECT * FROM todos'
        if completed is not None:
            query += ' WHERE completed = ?'
        with self.conn:
            cursor = self.conn.execute(query, (completed,)) if completed is not None else self.conn.cursor()
            return [dict(row) for row in cursor.fetchall()]

    def delete_todo(self, todo_id):
        with self.conn:
            self.conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))


# Example usage:
# manager = TodoManager()
# manager.add_todo('Buy groceries')
# print(manager.list_todos())
# manager.delete_todo(1)