from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

db = sqlite3.connect('todos.db', check_same_thread=False)
db.row_factory = sqlite3.Row

cur = db.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
db.commit()

def get_todos():
    cur.execute('SELECT * FROM todos')
    return cur.fetchall()

def add_todo(task):
    cur.execute('INSERT INTO todos (task) VALUES (?)', (task,))
    db.commit()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    task = data.get('task')
    if not task:
        return jsonify({'error': 'Missing task field'}), 400
    add_todo(task)
    return jsonify({'message': 'Todo created'}), 201

@app.route('/todos', methods=['GET'])
def list_todos():
    todos = get_todos()
    return jsonify([dict(todo) for todo in todos])

if __name__ == '__main__':
    app.run(debug=True)