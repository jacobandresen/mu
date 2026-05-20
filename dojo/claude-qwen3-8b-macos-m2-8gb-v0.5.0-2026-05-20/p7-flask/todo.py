from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
db = SQLAlchemy(app)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    task = data['task']
    new_todo = Todo(task=task)
    db.session.add(new_todo)
    db.session.commit()
    return jsonify({'task': task}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    return jsonify([{'id': todo.id, 'task': todo.task} for todo in todos])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)