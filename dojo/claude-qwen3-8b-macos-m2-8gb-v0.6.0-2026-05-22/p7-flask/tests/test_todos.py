from flask import Flask, json, testing


@pytest.fixture
def test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db = SQLAlchemy(app)

    with app.app_context():
        db.create_all()

    client = app.test_client()
    return client


def test_post_todo(test_app):
    response = test_app.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    assert 'id' in response.json


def test_get_todos(test_app):
    test_app.post('/todos', json={'task': 'Test task'})
    response = test_app.get('/todos')
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]['task'] == 'Test task'
