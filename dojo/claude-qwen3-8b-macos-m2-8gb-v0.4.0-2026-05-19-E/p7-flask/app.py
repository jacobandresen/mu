import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DATABASE = 'todos.db'

def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
        db.commit()

@app.before_first_request
def create_tables():
    init_db()

@app.route('/todos', methods=['POST'])
def add_todo():
    task = request.json.get('task')
    if not task:
        return jsonify({'error': 'Missing task'}), 400
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))
        conn.commit()
    return jsonify({'message': 'Todo added'}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        todos = conn.execute('SELECT * FROM todos').fetchall()
    return jsonify([dict(todo) for todo in todos])

if __name__ == '__main__':
    app.run(debug=True)