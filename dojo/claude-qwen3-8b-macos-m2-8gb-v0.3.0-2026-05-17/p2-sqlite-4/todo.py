import sqlite3

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('todos.db')

# Create a table to store todos
with conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL
        )
    ''')

# Insert a new todo entry
with conn:
    conn.execute('INSERT INTO todos (task) VALUES (?)', ('Complete this task',))

# Read and print the inserted todo entry
with conn:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM todos')
    rows = cursor.fetchall()
    print('Todos:')
    for row in rows:
        print(f'ID: {row[0]}, Task: {row[1]}')

# Close the connection
conn.close()