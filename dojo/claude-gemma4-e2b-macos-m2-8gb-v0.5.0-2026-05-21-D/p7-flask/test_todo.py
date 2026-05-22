import pytest
from app import app, db, Todo

@pytest.fixture
def client():
    # Set up the app context for testing
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory SQLite for testing
    app.config['TEARDOWN'] = True
    
    # Create a test database instance
    with app.app_context():
        db.create_all()
    
    # Create a test client
    app.config['TESTING'] = True
    with app.test_client(app) as client:
        yield client

@pytest.fixture
def db_setup(client):
    # This fixture ensures the database is clean before each test
    with app.app_context():
        db.session.rollback() # Ensure a clean state if needed
        yield

def test_create_todo(client):
    # Test POST /todos
    response = client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'task' in data
    assert data['task'] == 'Buy groceries'
    
    # Test GET /todos to verify creation
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 1
    assert todos[0]['task'] == 'Buy groceries'

def test_get_todos_empty(client):
    # Test GET /todos when empty
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 0

def test_get_todos_multiple(client):
    # Test POST multiple items
    client.post('/todos', json={'task': 'Task 1'})
    client.post('/todos', json={'task': 'Task 2'})
    
    response = client.get('/todos')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 2
    assert 'Task 1' in [t['task'] for t in todos]
    assert 'Task 2' in [t['task'] for t in todos]