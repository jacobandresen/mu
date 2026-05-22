import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DATABASE = 'todos.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL
        )
    ''')
    conn.commit()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({"error": "Missing 'task' field"}), 400
    
    task = data['task']
    conn = get_db()
    conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))
    conn.commit()
    return jsonify({"message": "Todo created", "task": task}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    conn = get_db()
    todos = conn.execute('SELECT * FROM todos')
    todos_list = [dict(row) for row in todos]
    return jsonify(todos_list)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)