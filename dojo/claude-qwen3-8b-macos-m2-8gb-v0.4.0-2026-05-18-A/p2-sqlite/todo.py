import sqlite3

with sqlite3.connect('todos.db') as conn:
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT, completed BOOLEAN)')
    cursor.execute('INSERT INTO todos (task, completed) VALUES (?, ?)', ('Buy milk', False))
    conn.commit()
    
    cursor.execute('SELECT * FROM todos')
    rows = cursor.fetchall()
    print("Inserted todos:")
    for row in rows:
        print(row)