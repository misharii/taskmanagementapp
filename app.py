from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

# Secret key for session management
app.secret_key = 'your_secret_key'

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'taskmanagement'

mysql = MySQL(app)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    # Check if "username" and "password" POST requests exist
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        # Fetch user from database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password,))
        account = cursor.fetchone()
        # If account exists
        if account:
            # Create session data
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['is_admin'] = account['is_admin']
            return redirect(url_for('home'))
        else:
            msg = 'Incorrect username/password!'
    return render_template('login.html', msg=msg)

@app.route('/')
def home():
    # Check if user is logged in
    if 'loggedin' in session:
        # Fetch tasks from database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            SELECT tasks.*, users.username AS assigned_user
            FROM tasks
            LEFT JOIN users ON tasks.assigned_to = users.id
        ''')
        tasks = cursor.fetchall()
        # Group tasks by status
        tasks_by_status = {'task': [], 'doing': [], 'done': []}
        for task in tasks:
            tasks_by_status[task['status']].append(task)
        return render_template(
            'home.html',
            username=session['username'],
            is_admin=session['is_admin'],
            tasks_by_status=tasks_by_status
        )
    return redirect(url_for('login'))

@app.route('/add_task', methods=['POST'])
def add_task():
    # Check if user is admin
    if 'loggedin' in session and session['is_admin']:
        title = request.form['title']
        description = request.form['description']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO tasks (title, description, status) VALUES (%s, %s, %s)', (title, description, 'task'))
        mysql.connection.commit()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    # Check if user is logged in
    if 'loggedin' in session:
        new_status = request.form['status']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Fetch current task details
        cursor.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
        task = cursor.fetchone()
        if not task:
            flash('Task not found.')
            return redirect(url_for('home'))
        # Permission check
        user_can_edit = False
        if session['is_admin']:
            user_can_edit = True
        elif task['status'] in ['doing', 'done']:
            if task['assigned_to'] == session['id']:
                user_can_edit = True
        else:
            user_can_edit = True  # Anyone can edit tasks in 'task' status
        if not user_can_edit:
            flash('You do not have permission to edit this task.')
            return redirect(url_for('home'))
        # Update task
        if new_status in ['doing', 'done']:
            # Assign task to current user
            cursor.execute(
                'UPDATE tasks SET status = %s, assigned_to = %s WHERE id = %s',
                (new_status, session['id'], task_id)
            )
        else:
            # Unassign task
            cursor.execute(
                'UPDATE tasks SET status = %s, assigned_to = NULL WHERE id = %s',
                (new_status, task_id)
            )
        mysql.connection.commit()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    # Clear session data
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)