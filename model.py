import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','hr','employee')),
            employee_id INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            department TEXT,
            role TEXT,
            salary REAL,
            joining_date TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            head TEXT
        )
    ''')

    # Seed default admin if not exists
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))

    c.execute("SELECT id FROM users WHERE username='hr'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  ('hr', generate_password_hash('hr123'), 'hr'))

    # Seed default departments if none exist
    c.execute("SELECT COUNT(*) FROM departments")
    if c.fetchone()[0] == 0:
        default_depts = [
            ('Engineering', 'Software and hardware development', ''),
            ('HR', 'Human resources and talent management', ''),
            ('Finance', 'Financial planning and accounting', ''),
            ('Marketing', 'Brand and marketing operations', ''),
            ('Operations', 'Business operations and logistics', ''),
        ]
        c.executemany(
            "INSERT INTO departments (name, description, head) VALUES (?,?,?)",
            default_depts
        )

    conn.commit()
    conn.close()

