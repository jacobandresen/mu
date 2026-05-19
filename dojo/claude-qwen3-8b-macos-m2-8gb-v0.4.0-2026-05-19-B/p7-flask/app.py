import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = 'todos.db'

def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL
            )
        ''')
        db.commit()
        db.close()

@app.before_first_request
def before_first_request():
    init_db()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({'error': 'Missing task field'}), 400
    task = data['task']
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO todos (task) VALUES (?)', (task,))
        conn.commit()
        todo_id = cursor.lastrowid
    return jsonify({'id': todo_id, 'task': task}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM todos')
        todos = [dict(row) for row in cursor.fetchall()]
    return jsonify(todos)

if __name__ == '__main__':
    app.run(debug=True)