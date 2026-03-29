import base64
import io
import json
import os
import sqlite3
import uuid
from datetime import date, datetime
from functools import wraps

import qrcode
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import close_db, get_db
from init_db import init_db


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["DATABASE"] = os.path.join(BASE_DIR, "attendance.db")

    with app.app_context():
        init_db()

    app.teardown_appcontext(close_db)

    @app.context_processor
    def inject_user():
        return {
            "current_user": session.get("user_name"),
            "current_role": session.get("user_role"),
            "current_year": datetime.now().year,
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            def wrapped_view(*args, **kwargs):
                if session.get("user_role") not in roles:
                    flash("You do not have permission to access that page.", "danger")
                    return redirect(url_for("login"))
                return view(*args, **kwargs)

            return wrapped_view

        return decorator

    def generate_qr_data_url(data):
        qr = qrcode.QRCode(version=1, box_size=8, border=3)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    def render_info_page(key):
        pages = {
            "terms": {
                "title": "Terms and Conditions",
                "eyebrow": "Legal",
                "headline": "Terms and Conditions",
                "description": "These terms explain how the attendance system should be used by teachers and students.",
                "sections": [
                    {
                        "title": "Account usage",
                        "body": "Use a valid email address and keep your password private. You are responsible for activity on your account.",
                    },
                    {
                        "title": "Attendance records",
                        "body": "Attendance is recorded based on QR sessions created by the teacher and scanned by the student.",
                    },
                    {
                        "title": "Acceptable use",
                        "body": "Do not attempt to bypass QR validation, impersonate another user, or misuse the application.",
                    },
                ],
            },
            "privacy": {
                "title": "Privacy Policy",
                "eyebrow": "Legal",
                "headline": "Privacy Policy",
                "description": "A short overview of what the system stores and how it uses that data.",
                "sections": [
                    {
                        "title": "Data stored",
                        "body": "The app stores name, email, role, class records, QR session data, and attendance marks in SQLite.",
                    },
                    {
                        "title": "Data purpose",
                        "body": "Data is only used to authenticate users, generate QR sessions, and show attendance history.",
                    },
                    {
                        "title": "Local deployment",
                        "body": "This project is designed for local or private deployment. No external analytics or tracking is included.",
                    },
                ],
            },
            "faqs": {
                "title": "FAQs",
                "eyebrow": "Support",
                "headline": "Frequently Asked Questions",
                "description": "Quick answers to the most common questions about the system.",
                "sections": [
                    {
                        "title": "How does attendance work?",
                        "body": "The teacher creates a QR session, the student scans it, and attendance is saved for that day.",
                    },
                    {
                        "title": "Can both teachers and students sign up?",
                        "body": "Yes. The signup page lets you choose either teacher or student during registration.",
                    },
                    {
                        "title": "Where do I see records?",
                        "body": "Teachers can review class attendance on the dashboard, and students can view their own history.",
                    },
                ],
            },
            "docs": {
                "title": "Documentation",
                "eyebrow": "Guide",
                "headline": "Documentation",
                "description": "A simple step-by-step guide for using Rizt Smart Attandence.",
                "sections": [
                    {
                        "title": "1. Create an account",
                        "body": "Open the signup page, choose teacher or student, and register with your email.",
                    },
                    {
                        "title": "2. Teacher flow",
                        "body": "Log in as a teacher, create a class, generate a QR session, and show the QR code to students.",
                    },
                    {
                        "title": "3. Student flow",
                        "body": "Log in as a student, open the QR scanner page, scan the code, and confirm the success message.",
                    },
                ],
            },
        }

        page = pages.get(key)
        if not page:
            return redirect(url_for("index"))

        return render_template("info_page.html", page=page, title=page["title"])

    @app.route("/")
    def index():
        if "user_id" in session:
            if session.get("user_role") == "teacher":
                return redirect(url_for("teacher_dashboard"))
            return redirect(url_for("student_scan"))
        return render_template("landing.html")

    @app.route("/terms")
    def terms():
        return render_info_page("terms")

    @app.route("/privacy")
    def privacy():
        return render_info_page("privacy")

    @app.route("/faqs")
    def faqs():
        return render_info_page("faqs")

    @app.route("/docs")
    def docs():
        return render_info_page("docs")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "")

            db = get_db()
            user = db.execute(
                """
                SELECT id, name, email, password, role
                FROM users
                WHERE email = ? AND role = ?
                """,
                (email, role),
            ).fetchone()

            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                session["user_role"] = user["role"]
                flash(f"Welcome back, {user['name']}!", "success")
                if user["role"] == "teacher":
                    return redirect(url_for("teacher_dashboard"))
                return redirect(url_for("student_scan"))

            flash("Invalid login details. Please check your email, password, and role.", "danger")

        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            role = request.form.get("role", "")

            if not name or not email or not password or not confirm_password:
                flash("Please fill in all the fields.", "warning")
                return render_template("signup.html")

            if role not in {"teacher", "student"}:
                flash("Please choose whether you are a teacher or a student.", "warning")
                return render_template("signup.html")

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return render_template("signup.html")

            db = get_db()
            existing_user = db.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if existing_user:
                flash("That email is already registered.", "danger")
                return render_template("signup.html")

            try:
                db.execute(
                    """
                    INSERT INTO users (name, email, password, role)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, email, generate_password_hash(password), role),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("Could not create your account. Please try again.", "danger")
                return render_template("signup.html")

            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("signup.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/teacher/dashboard", methods=["GET", "POST"])
    @login_required
    @role_required("teacher")
    def teacher_dashboard():
        db = get_db()
        teacher_id = session["user_id"]

        if request.method == "POST":
            class_name = request.form.get("class_name", "").strip()
            if not class_name:
                flash("Please enter a class name.", "warning")
            else:
                db.execute(
                    """
                    INSERT INTO classes (class_name, teacher_id)
                    VALUES (?, ?)
                    """,
                    (class_name, teacher_id),
                )
                db.commit()
                flash("Class created successfully.", "success")
                return redirect(url_for("teacher_dashboard"))

        classes = db.execute(
            """
            SELECT
                c.id,
                c.class_name,
                c.teacher_id,
                (
                    SELECT COUNT(*)
                    FROM qr_sessions qs
                    WHERE qs.class_id = c.id
                ) AS qr_count,
                (
                    SELECT qs.qr_code
                    FROM qr_sessions qs
                    WHERE qs.class_id = c.id
                    ORDER BY qs.created_at DESC, qs.id DESC
                    LIMIT 1
                ) AS latest_qr,
                (
                    SELECT qs.created_at
                    FROM qr_sessions qs
                    WHERE qs.class_id = c.id
                    ORDER BY qs.created_at DESC, qs.id DESC
                    LIMIT 1
                ) AS latest_created_at
            FROM classes c
            WHERE c.teacher_id = ?
            ORDER BY c.id DESC
            """,
            (teacher_id,),
        ).fetchall()

        class_ids = [row["id"] for row in classes]
        attendance_rows = []
        if class_ids:
            placeholders = ",".join("?" for _ in class_ids)
            attendance_rows = db.execute(
                f"""
                SELECT
                    a.id,
                    a.date,
                    a.status,
                    u.name AS student_name,
                    c.class_name
                FROM attendance a
                JOIN users u ON u.id = a.student_id
                JOIN classes c ON c.id = a.class_id
                WHERE a.class_id IN ({placeholders})
                ORDER BY a.id DESC
                LIMIT 20
                """,
                class_ids,
            ).fetchall()

        qr_previews = {}
        for row in classes:
            if row["latest_qr"]:
                qr_previews[row["id"]] = generate_qr_data_url(row["latest_qr"])

        return render_template(
            "teacher_dashboard.html",
            classes=classes,
            attendance_rows=attendance_rows,
            qr_previews=qr_previews,
        )

    @app.route("/teacher/classes/<int:class_id>/generate-qr", methods=["POST"])
    @login_required
    @role_required("teacher")
    def generate_qr(class_id):
        db = get_db()
        class_row = db.execute(
            "SELECT id, class_name, teacher_id FROM classes WHERE id = ? AND teacher_id = ?",
            (class_id, session["user_id"]),
        ).fetchone()

        if not class_row:
            flash("Class not found.", "danger")
            return redirect(url_for("teacher_dashboard"))

        temp_token = str(uuid.uuid4())
        cursor = db.execute(
            """
            INSERT INTO qr_sessions (class_id, qr_code)
            VALUES (?, ?)
            """,
            (class_id, temp_token),
        )
        session_id = cursor.lastrowid
        payload = json.dumps(
            {
                "class_id": class_id,
                "session_id": session_id,
            },
            separators=(",", ":"),
        )
        db.execute(
            "UPDATE qr_sessions SET qr_code = ? WHERE id = ?",
            (payload, session_id),
        )
        db.commit()
        flash(f"QR session created for {class_row['class_name']}.", "success")
        return redirect(url_for("teacher_dashboard"))

    @app.route("/teacher/classes/<int:class_id>/attendance")
    @login_required
    @role_required("teacher")
    def class_attendance(class_id):
        db = get_db()
        class_row = db.execute(
            "SELECT id, class_name FROM classes WHERE id = ? AND teacher_id = ?",
            (class_id, session["user_id"]),
        ).fetchone()

        if not class_row:
            flash("Class not found.", "danger")
            return redirect(url_for("teacher_dashboard"))

        records = db.execute(
            """
            SELECT a.date, a.status, u.name AS student_name
            FROM attendance a
            JOIN users u ON u.id = a.student_id
            WHERE a.class_id = ?
            ORDER BY a.date DESC, a.id DESC
            """,
            (class_id,),
        ).fetchall()

        sessions = db.execute(
            """
            SELECT qr_code, created_at
            FROM qr_sessions
            WHERE class_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (class_id,),
        ).fetchall()

        return render_template(
            "attendance_history.html",
            class_row=class_row,
            records=records,
            sessions=sessions,
        )

    @app.route("/student/dashboard")
    @login_required
    @role_required("student")
    def student_dashboard():
        db = get_db()
        classes = db.execute(
            """
            SELECT id, class_name
            FROM classes
            ORDER BY class_name ASC
            """
        ).fetchall()

        records = db.execute(
            """
            SELECT a.date, a.status, c.class_name
            FROM attendance a
            JOIN classes c ON c.id = a.class_id
            WHERE a.student_id = ?
            ORDER BY a.date DESC, a.id DESC
            """,
            (session["user_id"],),
        ).fetchall()

        return render_template("student_dashboard.html", records=records, classes=classes)

    @app.route("/student/scan")
    @login_required
    @role_required("student")
    def student_scan():
        db = get_db()
        classes = db.execute(
            """
            SELECT id, class_name
            FROM classes
            ORDER BY class_name ASC
            """
        ).fetchall()

        records = db.execute(
            """
            SELECT a.date, a.status, c.class_name
            FROM attendance a
            JOIN classes c ON c.id = a.class_id
            WHERE a.student_id = ?
            ORDER BY a.date DESC, a.id DESC
            """,
            (session["user_id"],),
        ).fetchall()

        return render_template("student_scan.html", records=records, classes=classes)

    @app.route("/student/mark-attendance", methods=["POST"])
    @login_required
    @role_required("student")
    def mark_attendance():
        qr_code = request.form.get("qr_code", "").strip()
        if not qr_code:
            flash("Please scan or enter a QR code token.", "warning")
            return redirect(url_for("student_dashboard"))

        try:
            qr_data = json.loads(qr_code)
            class_id = int(qr_data["class_id"])
            session_id = int(qr_data["session_id"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            flash("This QR code is not valid.", "danger")
            return redirect(url_for("student_dashboard"))

        db = get_db()
        qr_session = db.execute(
            """
            SELECT qs.id, qs.class_id, c.class_name
            FROM qr_sessions qs
            JOIN classes c ON c.id = qs.class_id
            WHERE qs.id = ? AND qs.class_id = ?
            """,
            (session_id, class_id),
        ).fetchone()

        if not qr_session:
            flash("This QR code is not valid.", "danger")
            return redirect(url_for("student_dashboard"))

        today = date.today().isoformat()
        already_marked = db.execute(
            """
            SELECT id
            FROM attendance
            WHERE student_id = ? AND class_id = ? AND date = ?
            """,
            (session["user_id"], qr_session["class_id"], today),
        ).fetchone()

        if already_marked:
            flash(f"Attendance already recorded for {qr_session['class_name']} today.", "info")
            return redirect(url_for("student_dashboard"))

        db.execute(
            """
            INSERT INTO attendance (student_id, class_id, date, status)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], qr_session["class_id"], today, "Present"),
        )
        db.commit()
        flash(f"Attendance marked for {qr_session['class_name']} on {today}.", "success")
        return redirect(url_for("student_scan"))

    @app.route("/api/attendance/scan", methods=["POST"])
    @login_required
    @role_required("student")
    def api_scan_attendance():
        payload = request.get_json(silent=True) or {}
        qr_code = (payload.get("qr_code") or "").strip()
        if not qr_code:
            return jsonify({"success": False, "message": "QR data is required."}), 400

        try:
            qr_data = json.loads(qr_code)
            class_id = int(qr_data["class_id"])
            session_id = int(qr_data["session_id"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return jsonify({"success": False, "message": "Invalid QR payload."}), 400

        db = get_db()
        qr_session = db.execute(
            """
            SELECT qs.id, qs.class_id, c.class_name
            FROM qr_sessions qs
            JOIN classes c ON c.id = qs.class_id
            WHERE qs.id = ? AND qs.class_id = ?
            """,
            (session_id, class_id),
        ).fetchone()

        if not qr_session:
            return jsonify({"success": False, "message": "QR session not found."}), 404

        today = date.today().isoformat()
        already_marked = db.execute(
            """
            SELECT id
            FROM attendance
            WHERE student_id = ? AND class_id = ? AND date = ?
            """,
            (session["user_id"], qr_session["class_id"], today),
        ).fetchone()

        if already_marked:
            return jsonify(
                {
                    "success": False,
                    "message": f"Attendance already recorded for {qr_session['class_name']} today.",
                }
            ), 409

        db.execute(
            """
            INSERT INTO attendance (student_id, class_id, date, status)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], qr_session["class_id"], today, "Present"),
        )
        db.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Attendance marked for {qr_session['class_name']} on {today}.",
                "class_name": qr_session["class_name"],
                "date": today,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
