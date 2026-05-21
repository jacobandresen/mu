Flask
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DATABASE = 'todos.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({"error": "Missing 'task' field"}), 400
    
    task = data['task']
    conn = get_db()
    conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Todo created", "task": task}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    conn = get_db()
    todos = conn.execute('SELECT * FROM todos').fetchall()
    conn.close()
    
    todos_list = []
    for todo in todos:
        todos_list.append({
            'id': todo['id'],
            'task': todo['task']
        })
    return jsonify(todos_list)

if __name__ == '__main__':
    # In a real scenario, you might use a proper WSGI server. 
    # For testing purposes, we keep it simple.
    app.run(debug=True)