from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import shutil
from database import get_db_connection, init_db

app = Flask(__name__)

# Secret key for session management
app.secret_key = 'your_secret_key'

# Initialize the database
init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    try:
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
            username = request.form['username']
            password = request.form['password']
            conn = get_db_connection()
            cursor = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password,))
            account = cursor.fetchone()
            conn.close()
            if account:
                session['loggedin'] = True
                session['id'] = account['id']
                session['username'] = account['username']
                session['is_admin'] = account['is_admin']
                return redirect(url_for('home'))
            else:
                msg = 'Incorrect username/password!'
    except sqlite3.Error as e:
        print(f"Error: {e}")
        msg = 'Database error occurred.'
    return render_template('login.html', msg=msg)

@app.route('/')
def home():
    if 'loggedin' in session:
        try:
            conn = get_db_connection()
            cursor = conn.execute('''
                SELECT tasks.*, users.username AS assigned_user
                FROM tasks
                LEFT JOIN users ON tasks.assigned_to = users.id
            ''')
            tasks = cursor.fetchall()
            conn.close()
            tasks_by_status = {'task': [], 'doing': [], 'done': []}
            for task in tasks:
                tasks_by_status[task['status']].append(task)
            return render_template(
                'home.html',
                username=session['username'],
                is_admin=session['is_admin'],
                tasks_by_status=tasks_by_status
            )
        except sqlite3.Error as e:
            flash(f"Error: {e}")
            return redirect(url_for('login'))
    return redirect(url_for('login'))

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'loggedin' in session and session['is_admin']:
        title = request.form['title']
        description = request.form['description']
        conn = get_db_connection()
        conn.execute('INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)', (title, description, 'task'))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    if 'loggedin' in session:
        new_status = request.form['status']
        conn = get_db_connection()
        cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        if not task:
            flash('Task not found.')
            conn.close()
            return redirect(url_for('home'))
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
            conn.close()
            return redirect(url_for('home'))
        if new_status in ['doing', 'done']:
            conn.execute(
                'UPDATE tasks SET status = ?, assigned_to = ? WHERE id = ?',
                (new_status, session['id'], task_id)
            )
        else:
            conn.execute(
                'UPDATE tasks SET status = ?, assigned_to = NULL WHERE id = ?',
                (new_status, task_id)
            )
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if 'loggedin' in session and session['is_admin']:
        conn = get_db_connection()
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        flash('Task deleted successfully!')
        return redirect(url_for('home'))
    flash('You do not have permission to delete this task.')
    return redirect(url_for('home'))

@app.route('/backup_db', methods=['GET'])
def backup_db():
    if 'loggedin' in session and session['is_admin']:  # Ensure only admins can access this
        try:
            # Path to the backup file
            backup_path = 'backup/database_backup.sql'

            # Ensure the backup directory exists
            if not os.path.exists('backup'):
                os.makedirs('backup')

            # Connect to the SQLite database
            conn = sqlite3.connect('database.db')

            # Create a .sql file containing the SQL dump
            with open(backup_path, 'w') as f:
                for line in conn.iterdump():
                    f.write(f'{line}\n')

            conn.close()

            # Send the SQL dump file as a .txt download
            return send_file(backup_path, as_attachment=True, download_name="database_backup.txt")

        except Exception as e:
            flash(f"Error occurred while creating a backup: {e}")
            return redirect(url_for('home'))
    else:
        flash('You do not have permission to access this page.')
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
