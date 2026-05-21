# test_todos.py
import pytest
import sqlite3
from todo import app, get_db, init_db

@pytest.fixture
def db():
    # Setup: Initialize DB and get connection
    init_db()
    conn = sqlite3.connect('todos.db')
    conn.row_factory = sqlite3.Row
    yield conn
    # Teardown: Cleanup (optional, but good practice for tests)
    conn.close()

@pytest.fixture
def app_client():
    # Setup: Create a test client
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_create_todo(app_client):
    # Test POST /todos
    response = app_client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'id' in data
    assert 'task' in data
    assert data['task'] == 'Buy groceries'

def test_get_todos(app_client):
    # Create a todo first
    response = app_client.post('/todos', json={'task': 'Learn Flask'})
    assert response.status_code == 201
    
    # Test GET /todos
    response = app_client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['task'] == 'Learn Flask'

def test_get_todos_empty(app_client):
    # Test GET /todos on an empty DB
    response = app_client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 0