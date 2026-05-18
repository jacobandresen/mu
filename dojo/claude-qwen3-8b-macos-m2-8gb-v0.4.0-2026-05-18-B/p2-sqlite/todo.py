import sqlite3

conn = sqlite3.connect('todos.db')
cursor = conn.cursor()

# Create todos table if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        completed BOOLEAN DEFAULT FALSE
    )
''')

# Insert a new todo item
cursor.execute('INSERT INTO todos (task) VALUES (?)', ('Buy milk',))
conn.commit()

# Verify the inserted item exists
cursor.execute('SELECT * FROM todos WHERE task = ?', ('Buy milk',))
result = cursor.fetchone()

print("Inserted todo:", result)

conn.close()