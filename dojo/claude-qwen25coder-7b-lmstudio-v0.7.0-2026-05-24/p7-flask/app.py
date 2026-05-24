from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
db.init_app(app)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(80), nullable=False)

def create_todo(task):
    todo = Todo(task=task)
    db.session.add(todo)
    db.session.commit()
    return jsonify({'message': 'Todo created successfully'}), 201

def get_todos():
    todos = Todo.query.all()
    return jsonify([{'id': todo.id, 'task': todo.task} for todo in todos])

@app.route('/todos', methods=['POST'])
def add_todo():
    task = request.json.get('task')
    if not task:
        return jsonify({'message': 'Task is required'}), 400
    return create_todo(task)

@app.route('/todos', methods=['GET'])
def list_todos():
    return get_todos()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)