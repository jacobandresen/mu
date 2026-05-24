import pytest
from app import db, Todo, create_app

@pytest.fixture(scope='module')
def client():
    app = create_app()
    with app.app_context():
        db.create_all()
    yield app.test_client()
    with app.app_context():
        db.session.remove()
        db.drop_all()

def test_create_todo(client):
    response = client.post('/todos', json={'task': 'Buy groceries'}, content_type='application/json')
    assert response.status_code == 201
    data = response.get_json()
    assert data['id'] is not None
    assert data['task'] == 'Buy groceries'

def test_get_todos(client):
    client.post('/todos', json={'task': 'Buy groceries'}, content_type='application/json')
    response = client.get('/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['id'] is not None
    assert data[0]['task'] == 'Buy groceries'