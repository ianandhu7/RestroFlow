import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime
from database import get_db_connection, init_db

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "supersecret")

def login_required(role="any"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_authorized = False
            if role == "admin" and session.get('is_admin'): 
                is_authorized = True
            elif role == "waiter" and session.get('waiter_id'): 
                is_authorized = True
            elif role == "any" and (session.get('is_admin') or session.get('waiter_id')): 
                is_authorized = True

            if is_authorized:
                return f(*args, **kwargs)

            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "message": "Authentication required."}), 401
            else:
                flash("You must be logged in to view this page.", "error")
                return redirect(url_for('login'))
        return decorated_function
    return decorator

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        conn, db_type = get_db_connection()
        conn.close()
        return jsonify({
            "status": "healthy",
            "database": db_type,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route("/")
@login_required(role="any")
def index():
    if session.get('is_admin'):
        return redirect(url_for('dashboard'))
    elif session.get('waiter_id'):
        return redirect(url_for('waiter_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USER and password == ADMIN_PASSWORD:
            session.clear()
            session['is_admin'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        
        conn, db_type = get_db_connection()
        try:
            cursor = conn.cursor()
            if db_type == 'postgresql':
                cursor.execute('SELECT * FROM waiters WHERE username = %s', (username,))
            else:
                cursor.execute('SELECT * FROM waiters WHERE username = ?', (username,))
            waiter = cursor.fetchone()
            
            if waiter and check_password_hash(waiter['password_hash'], password):
                session.clear()
                session['waiter_id'] = waiter['id']
                session['waiter_username'] = waiter['username']
                return redirect(url_for('waiter_dashboard'))
        finally:
            conn.close()
            
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required("any")
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required(role="admin")
def dashboard():
    return render_template('admin.html', waiters=[], tables=[], current_filters={})

@app.route('/waiter')
@login_required(role="waiter")
def waiter_dashboard():
    return render_template('waiter.html', username=session.get('waiter_username', 'Waiter'))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)