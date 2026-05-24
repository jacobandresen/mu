# todo_manager.py
import sqlite3

def add_todo(todo):
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, todo TEXT)''')
    c.execute("INSERT INTO todos (todo) VALUES (?)", (todo,))
    conn.commit()
    conn.close()

def list_todos():
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM todos''')
    todos = c.fetchall()
    conn.close()
    return todos

def delete_todo(todo_id):
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    conn.commit()
    conn.close()