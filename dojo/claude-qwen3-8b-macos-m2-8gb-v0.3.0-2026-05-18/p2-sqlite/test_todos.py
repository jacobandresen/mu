import sqlite3

def test_create_table():
    conn = sqlite3.connect('todos.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='todos'
    """)
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Table 'todos' not created"


def test_insert_todo():
    conn = sqlite3.connect('todos.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO todos (task)
        VALUES (?)
    """, ('Test task',))
    conn.commit()
    conn.close()


def test_read_todos():
    conn = sqlite3.connect('todos.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO todos (task)
        VALUES ('Task 1'), ('Task 2'), ('Task 3')
    """)
    conn.commit()
    conn.close()
