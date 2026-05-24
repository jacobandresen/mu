# todo_manager.py
import sqlite3

def create_connection(db_file):
    conn = None;
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    return conn

def add_todo(conn, todo):
    sql = ''' INSERT INTO todos(todo) VALUES(?) '''
    cur = conn.cursor()
    cur.execute(sql, (todo,))
    conn.commit()
    return cur.lastrowid

def list_todos(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM todos")
    rows = cur.fetchall()
    for row in rows:
        print(row)

def delete_todo(conn, todo_id):
    sql = 'DELETE FROM todos WHERE id=?'
    cur = conn.cursor()
    cur.execute(sql, (todo_id,))
    conn.commit()