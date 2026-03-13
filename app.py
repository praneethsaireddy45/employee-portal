from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db, init_db
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'ku_secret_key_2024_secure'

# ── Decorators ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Auth ────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['employee_id'] = user['employee_id']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ── Dashboard ────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    stats = {}
    if session['role'] in ('admin', 'hr'):
        stats['total'] = db.execute('SELECT COUNT(*) FROM employees').fetchone()[0]
        stats['departments'] = db.execute('SELECT COUNT(DISTINCT department) FROM employees').fetchone()[0]
        stats['users'] = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        dept_rows = db.execute('SELECT department, COUNT(*) as cnt FROM employees GROUP BY department').fetchall()
        stats['dept_data'] = [dict(r) for r in dept_rows]
        recent = db.execute('SELECT * FROM employees ORDER BY id DESC LIMIT 5').fetchall()
    else:
        # Employee: show only their own record
        emp_id = session.get('employee_id')
        recent = db.execute('SELECT * FROM employees WHERE id=?', (emp_id,)).fetchall() if emp_id else []
        stats['total'] = 1
        stats['departments'] = 0
        stats['users'] = 0
        stats['dept_data'] = []
    db.close()
    return render_template('dashboard.html', stats=stats, recent=recent)

# ── Employees ────────────────────────────────────────────────────────────────

@app.route('/employees')
@login_required
def employees():
    role = session['role']
    search = request.args.get('q', '').strip()
    db = get_db()
    if role == 'employee':
        emp_id = session.get('employee_id')
        rows = db.execute('SELECT * FROM employees WHERE id=?', (emp_id,)).fetchall() if emp_id else []
    elif search:
        like = f'%{search}%'
        rows = db.execute(
            'SELECT * FROM employees WHERE name LIKE ? OR email LIKE ? OR department LIKE ? OR role LIKE ?',
            (like, like, like, like)
        ).fetchall()
    else:
        rows = db.execute('SELECT * FROM employees ORDER BY id DESC').fetchall()
    db.close()
    return render_template('employees.html', employees=rows, search=search)

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'hr')
def add_employee():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        department = request.form['department'].strip()
        role = request.form['role'].strip()
        salary = request.form['salary'].strip()
        joining_date = request.form['joining_date']
        db = get_db()
        try:
            db.execute(
                'INSERT INTO employees (name,email,phone,department,role,salary,joining_date) VALUES (?,?,?,?,?,?,?)',
                (name, email, phone, department, role, float(salary) if salary else 0, joining_date)
            )
            db.commit()
            flash('Employee added successfully!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
        return redirect(url_for('employees'))
    return render_template('add_employee.html')

@app.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'hr')
def edit_employee(emp_id):
    db = get_db()
    emp = db.execute('SELECT * FROM employees WHERE id=?', (emp_id,)).fetchone()
    if not emp:
        db.close()
        flash('Employee not found.', 'danger')
        return redirect(url_for('employees'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        department = request.form['department'].strip()
        role = request.form['role'].strip()
        salary = request.form['salary'].strip()
        joining_date = request.form['joining_date']
        try:
            db.execute(
                'UPDATE employees SET name=?,email=?,phone=?,department=?,role=?,salary=?,joining_date=? WHERE id=?',
                (name, email, phone, department, role, float(salary) if salary else 0, joining_date, emp_id)
            )
            db.commit()
            flash('Employee updated successfully!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
        return redirect(url_for('employees'))
    db.close()
    return render_template('edit_employee.html', emp=emp)

@app.route('/employees/delete/<int:emp_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_employee(emp_id):
    db = get_db()
    db.execute('DELETE FROM employees WHERE id=?', (emp_id,))
    db.commit()
    db.close()
    flash('Employee deleted.', 'info')
    return redirect(url_for('employees'))

# ── User Management (Admin only) ─────────────────────────────────────────────

@app.route('/users')
@login_required
@roles_required('admin')
def users():
    db = get_db()
    rows = db.execute('SELECT u.*, e.name as emp_name FROM users u LEFT JOIN employees e ON u.employee_id=e.id').fetchall()
    db.close()
    return render_template('users.html', users=rows)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def add_user():
    db = get_db()
    employees = db.execute('SELECT id, name FROM employees ORDER BY name').fetchall()
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role']
        emp_id = request.form.get('employee_id') or None
        try:
            db.execute('INSERT INTO users (username,password,role,employee_id) VALUES (?,?,?,?)',
                       (username, generate_password_hash(password), role, emp_id))
            db.commit()
            flash('User created!', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
        return redirect(url_for('users'))
    db.close()
    return render_template('add_user.html', employees=employees)

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_user(user_id):
    if user_id == session['user_id']:
        flash("You can't delete yourself.", 'warning')
        return redirect(url_for('users'))
    db = get_db()
    user = db.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
    if user and user['role'] == 'admin' and session['role'] != 'admin':
        flash("Cannot delete admin accounts.", 'danger')
        db.close()
        return redirect(url_for('users'))
    db.execute('DELETE FROM users WHERE id=?', (user_id,))
    db.commit()
    db.close()
    flash('User deleted.', 'info')
    return redirect(url_for('users'))

# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050)
