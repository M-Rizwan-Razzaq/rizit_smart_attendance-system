import os
import sqlite3

from werkzeug.security import generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "attendance.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('teacher', 'student'))
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL,
    teacher_id INTEGER NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qr_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    qr_code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
);
"""


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys = ON")

    teacher_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'teacher'"
    ).fetchone()[0]
    student_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]

    if teacher_count == 0:
        conn.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Demo Teacher",
                "teacher@example.com",
                generate_password_hash("teacher123"),
                "teacher",
            ),
        )

    if student_count == 0:
        conn.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Demo Student",
                "student@example.com",
                generate_password_hash("student123"),
                "student",
            ),
        )

    teacher_id = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("teacher@example.com",),
    ).fetchone()

    class_count = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    if teacher_id and class_count == 0:
        conn.execute(
            """
            INSERT INTO classes (class_name, teacher_id)
            VALUES (?, ?)
            """,
            ("Software Engineering", teacher_id[0]),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DATABASE}")
