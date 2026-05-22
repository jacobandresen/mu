# todo_test.py
import pytest
import sqlite3
import json
from todo import app, get_db, init_db, DATABASE

@pytest.fixture
def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def setup_db(db):
    # Ensure the table exists before tests run
    init_db()

@pytest.fixture
def client():
    # Set up the app for testing
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_create_todo(client):
    # Test POST /todos
    response = client.post('/todos', data=json.dumps({'task': 'Test task'}), content_type='application/json')
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'id' in data
    assert 'task' in data
    assert isinstance(data['id'], int)
    assert isinstance(data['task'], str)

def test_get_todos(client):
    # Create a todo item first
    response = client.post('/todos', data=json.dumps({'task': 'First todo'}), content_type='application/json'))
    assert response.status_code == 201
    
    # Get all todos
    response = client.get('/todos')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['task'] == 'First todo'

def test_get_empty_todos(client):
    # Ensure no todos exist initially
    response = client.get('/todos')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 0