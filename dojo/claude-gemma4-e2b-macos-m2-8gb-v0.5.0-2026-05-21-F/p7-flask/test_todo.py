import pytest
from todo import app, db, init_db

@pytest.fixture(scope='session')
def client():
    # Set up the app context for testing
    with app.test_client() as client:
        # Ensure the database is initialized before tests run
        with app.app_context():
            db.create_all()
        yield client

@pytest.fixture(scope='function')
def db_session():
    # Setup a fresh session for each test
    with app.app_context():
        # Create a session for the test
        session = db.session
        yield session

def test_create_todo(client):
    response = client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'task' in data
    assert data['task'] == 'Buy groceries'
    assert 'id' in data
    assert isinstance(data['id'], int)

def test_get_todos(client):
    # Create a todo first
    response = client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    
    # Get all todos
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert 'task' in data[0]

def test_get_todos_empty(client):
    # Ensure the database is empty before testing
    with app.app_context():
        # Clear existing data if necessary (though create_all() handles initial setup)
        # For this test, we rely on the fixture setup to ensure a clean state per test run if possible, 
        # but since we are using a shared DB file, we need to ensure we test the GET endpoint correctly.
        pass
        
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0