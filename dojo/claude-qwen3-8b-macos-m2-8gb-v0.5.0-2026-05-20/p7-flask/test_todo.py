import pytest
from todo import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        yield client


def test_post_todo(client):
    response = client.post('/todos', json={'task': 'Test Task'})
    assert response.status_code == 201
    data = response.get_json()
    assert data['task'] == 'Test Task'
    assert data['id'] is not None


def test_get_todos(client):
    client.post('/todos', json={'task': 'First Task'})
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['task'] == 'First Task'