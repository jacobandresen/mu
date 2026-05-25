import pytest
from app import app, db, Todo

@pytest.fixture(scope='module')
def client():
    with app.test_client() as c:
        yield c

def test_create_todo(client):
    response = client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'id' in data
    assert data['task'] == 'Buy groceries'

def test_get_todos(client):
    response = client.post('/todos', json={'task': 'Buy groceries'})
    assert response.status_code == 201
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['task'] == 'Buy groceries'