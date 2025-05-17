from flask import Flask, send_from_directory, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Configure the PostgreSQL database URI
# IMPORTANT: Replace 'youruser', 'yourpassword', 'localhost', '5432' with your actual PostgreSQL credentials and database name if different.
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Birdsinthebank2!@localhost:5432/sidequest'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')
ASSETS_DIR = os.path.join(BASE_DIR, '..', 'assets') # Path to the assets directory

# --- Database Models ---
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    task_type = db.Column(db.String(20), nullable=False, default='todo') # 'todo', 'daily', 'habit'
    difficulty = db.Column(db.String(20), nullable=False, default='medium') # 'easy', 'medium', 'hard'
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    # user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Will add when User model is ready

    def __repr__(self):
        return f'<Task {self.id}: {self.title} ({self.task_type}, {self.difficulty})>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'notes': self.notes,
            'task_type': self.task_type,
            'difficulty': self.difficulty,
            'is_completed': self.is_completed
        }

# --- API Routes ---
@app.route('/')
def home():
    return "Hello from SideQuest Backend!"

@app.route('/preview')
def preview():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/assets/<path:filename>') # Route to serve static assets
def serve_asset(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    if not data or not 'title' in data:
        return jsonify({'error': 'Missing title'}), 400
    
    task_type = data.get('task_type', 'todo') 
    if task_type not in ['todo', 'daily', 'habit']:
        return jsonify({'error': 'Invalid task_type. Must be todo, daily, or habit.'}), 400

    difficulty = data.get('difficulty', 'medium')
    if difficulty not in ['easy', 'medium', 'hard']:
        return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard.'}), 400

    new_task = Task(
        title=data['title'], 
        notes=data.get('notes'), 
        task_type=task_type,
        difficulty=difficulty
    )
    db.session.add(new_task)
    db.session.commit()
    return jsonify(new_task.to_dict()), 201

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    # Get the task_type from query parameters (e.g., /api/tasks?type=todo)
    task_type_filter = request.args.get('type')

    query = Task.query
    if task_type_filter:
        if task_type_filter not in ['todo', 'daily', 'habit']:
            return jsonify({'error': 'Invalid type filter. Must be todo, daily, or habit.'}), 400
        query = query.filter_by(task_type=task_type_filter)
    else:
        # If no type filter is explicitly provided, default to 'todo' tasks for now.
        # Consider changing this if all tasks of all types should be returned by default.
        query = query.filter_by(task_type='todo') 

    tasks = query.all()
    return jsonify([task.to_dict() for task in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    if 'is_completed' in data and isinstance(data['is_completed'], bool):
        task.is_completed = data['is_completed']
    
    # Future: Could add updates for title, notes, difficulty, type here
    # if 'title' in data: task.title = data['title']
    # if 'notes' in data: task.notes = data['notes']
    # if 'difficulty' in data: task.difficulty = data['difficulty'] 
    # if 'task_type' in data: task.task_type = data['task_type']

    db.session.commit()
    return jsonify(task.to_dict()), 200

# --- Main and DB Init ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Create database tables if they don't exist
    app.run(debug=True) 