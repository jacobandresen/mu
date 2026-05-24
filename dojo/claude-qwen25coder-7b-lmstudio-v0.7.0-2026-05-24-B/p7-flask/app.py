from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('todos.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/todos', methods=['POST'])
def add_todo():
    task = request.json['task']
    conn = get_db_connection()
    conn.execute('INSERT INTO todos (task) VALUES (?)', (task,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Todo added'}), 201

@app.route('/todos', methods=['GET'])
def list_todos():
    conn = get_db_connection()
    todos = conn.execute('SELECT * FROM todos').fetchall()
    conn.close()
    return jsonify([dict(todo) for todo in todos])

if __name__ == '__main__':
    app.run(debug=True)