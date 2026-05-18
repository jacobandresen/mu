from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Initialize SQLite database
conn = sqlite3.connect('todos.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL)')
conn.commit()

def get_todos():
    cur.execute('SELECT * FROM todos')
    return cur.fetchall()

def add_todo(task):
    cur.execute('INSERT INTO todos (task) VALUES (?)', (task,))
    conn.commit()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    task = data.get('task')
    if not task:
        return jsonify({'error': 'Missing task field'}), 400
    add_todo(task)
    return jsonify({'message': 'Todo created'}), 201

@app.route('/todos', methods=['GET'])
def get_todos_route():
    todos = get_todos()
    return jsonify([{'id': todo[0], 'task': todo[1]} for todo in todos])

if __name__ == '__main__':
    app.run(debug=True)
