# Rizt Smart Attandence

A Flask + SQLite project for QR-based student attendance tracking.

## Features

- Teacher login
- Student login
- SQLite database
- QR session generation for each class
- Student attendance marking using QR codes
- Bootstrap-based frontend with HTML, CSS, and JavaScript

## Project Structure

```text
.
├── app.py
├── attendance.db
├── database.py
├── init_db.py
├── requirements.txt
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── templates/
    ├── attendance_history.html
    ├── base.html
    ├── login.html
    ├── student_dashboard.html
    └── teacher_dashboard.html
```

## Database Tables

The app creates these tables in SQLite:

1. `users (id, name, email, password, role)`
2. `classes (id, class_name, teacher_id)`
3. `qr_sessions (id, class_id, qr_code, created_at)`
4. `attendance (id, student_id, class_id, date, status)`

## Demo Logins

- Teacher: `teacher@example.com` / `teacher123`
- Student: `student@example.com` / `student123`

## Run Instructions

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:

   ```bash
   python init_db.py
   ```

4. Run the app:

   ```bash
   python app.py
   ```

5. Open the app in your browser:

   ```text
   http://127.0.0.1:5000
   ```

## Notes

- Teachers can create classes and generate QR sessions.
- Students can scan the QR code or paste the token into the attendance form.
- Attendance is recorded once per student, class, and day.
