import sqlite3
def init_db():
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT)")
    conn.commit()
    conn.close()
def add_task(task):
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("INSERT INTO todos (task) VALUES (?)", (task,))
    conn.commit()
    conn.close()
def list_tasks():
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("SELECT * FROM todos")
    tasks = c.fetchall()
    conn.close()
    return tasks
def delete_task(task_id):
    conn = sqlite3.connect('todos.db')
    c = conn.cursor()
    c.execute("DELETE FROM todos WHERE id=?", (task_id,))
    conn.commit()
    conn.close()