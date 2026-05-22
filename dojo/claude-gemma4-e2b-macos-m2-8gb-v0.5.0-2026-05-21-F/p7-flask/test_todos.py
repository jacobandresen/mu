import pytest
from app import app, db
from app import Todo

@pytest.fixture
def client():
    # Set up the app context for testing
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in-memory SQLite for testing
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.test_client() as client:
        # Create tables in the test database
        with app.app_context():
            db.create_all()
        yield client

@pytest.fixture
def db_session(client):
    # This fixture is not strictly necessary for this setup but kept for structure
    with app.app_context():
        # Setup for testing
        pass

def test_create_todo(client):
    # Test POST /todos
    response = client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'task' in data
    assert data['task'] == 'Test task'

def test_get_todos(client):
    # Create a todo first
    response = client.post('/todos', json={'task': 'Another task'})
    assert response.status_code == 201
    
    # Get all todos
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    
    # Check if the created tasks are present (order might vary, check content)
    tasks = [todo['task'] for todo in data]
    assert 'Another task' in tasks
    assert 'Test task' in tasks