from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Todo(db.Model):
    id = db.Column(db.Integer, default=db.rowid, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'task': self.task,
            'created_at': self.created_at.isoformat()
        }

def init_db(app):
    with app.app_context():
        db.create_all()

@app.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({"error": "Missing 'task' field"}), 400
    
    new_todo = Todo(task=data['task'])
    db.session.add(new_todo)
    db.session.commit()
    return jsonify(new_todo.to_dict()), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    todo_list = [todo.to_dict() for todo in todos]
    return jsonify(todo_list)

if __name__ == '__main__':
    # Ensure database and tables are created when running the app directly
    with app.app_context():
        init_db(app)
    app.run(debug=True)