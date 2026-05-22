import pytest
import sqlite3
import json

# Mock Flask app for testing
from flask import Flask, jsonify, request

# Test data
TEST_TODOS = [
    {'id': 1, 'task': 'Learn Flask'},
    {'id': 2, 'task': 'Learn SQLite'}
]

# Mock database
def get_db():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE todos (
            id INTEGER PRIMARY KEY,
            task TEXT NOT NULL
        );
        INSERT INTO todos (id, task) VALUES (1, 'Learn Flask');
        INSERT INTO todos (id, task) VALUES (2, 'Learn SQLite');
    ''')
    return conn

# Mock Flask app
app = Flask(__name__)

# Routes
@app.route('/todos', methods=['GET'])
def get_todos():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, task FROM todos")
    rows = cursor.fetchall()
    todos = []
    for row in rows:
        todos.append({'id': row[0], 'task': row[1]})
    return jsonify(todos)

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({'error': 'Missing task field'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task) VALUES (?)", (data['task'],))
    conn.commit()
    new_id = cursor.lastrowid
    return jsonify({'id': new_id, 'task': data['task']}), 201

# Test the routes
@pytest.fixture
def app_instance():
    return app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

def test_get_todos(client):
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]['task'] == 'Learn Flask'
    assert data[1]['task'] == 'Learn SQLite'

def test_create_todo(client):
    new_task = 'Learn Python'
    response = client.post('/todos', json={'task': new_task})
    assert response.status_code == 201
    data = response.get_json()
    assert data['task'] == new_task
    assert data['id'] is not None

# Run the tests
if __name__ == '__main__':
    test_get_todos(None)
    test_create_todo(None)