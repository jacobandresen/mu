from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import pytest

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'Todo({self.task})'

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    new_todo = Todo(task=data['task'])
    db.session.add(new_todo)
    db.session.commit()
    return {'id': new_todo.id}, 201

@app.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    return [{'id': todo.id, 'task': todo.task} for todo in todos], 200

# Test setup
@pytest.fixture(scope='function')
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture(scope='function')
def test_client(test_app):
    return test_app.test_client()

# Test cases
def test_create_todo(test_client):
    response = test_client.post('/todos', json={'task': 'Test task'})
    assert response.status_code == 201
    assert response.json['id'] == 1

def test_get_todos(test_client):
    test_client.post('/todos', json={'task': 'First task'})
    test_client.post('/todos', json={'task': 'Second task'})
    response = test_client.get('/todos')
    assert response.status_code == 200
    assert len(response.json) == 2
    assert response.json[0]['task'] == 'First task'
    assert response.json[1]['task'] == 'Second task'