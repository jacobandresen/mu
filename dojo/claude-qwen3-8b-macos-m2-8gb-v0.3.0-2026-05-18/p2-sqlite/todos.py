import sqlite3

# Create the todos table if it doesn't exist
conn = sqlite3.connect('todos.db')
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
conn.commit()
conn.close()

# Insert a todo entry
conn = sqlite3.connect('todos.db')
cursor = conn.cursor()
cursor.execute('INSERT INTO todos (task) VALUES (?)', ('Test task',))
conn.commit()
conn.close()

# Read all todos
conn = sqlite3.connect('todos.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM todos')
results = cursor.fetchall()
conn.close()
