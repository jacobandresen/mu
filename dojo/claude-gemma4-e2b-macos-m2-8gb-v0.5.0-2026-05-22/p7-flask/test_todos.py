import pytest
from app import app, get_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['TEST_DATABASE_NAME'] = 'todos.db'
    app.config['TEST_ENV_IGNORE_DEBUG'] = True
    app.config['TEST_DATABASE_NAME'] = 'todos.db'
    with app.test_client() as client:
        yield client

def test_create_todo(client):
    response = client.post('/todos', json={'task': 'Buy milk'})
    assert response.status_code == 201
    assert response.json['message'] == 'Todo created'
    assert response.json['task'] == 'Buy milk'

def test_get_todos(client):
    # Ensure there is at least one todo before testing GET
    # We create one manually for a more robust test if needed, but for simplicity, we test the flow.
    
    # Create a todo first
    response = client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    
    # Now get all todos
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.json()
    assert isinstance(todos, list)
    assert len(todos) == 1
    assert todos[0]['task'] == 'Test task'