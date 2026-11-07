# Student Management System

A web app built with Python, Flask, SQLite and Bootstrap to manage students, courses, enrollment, attendance and marks.

## Features
- Admin login with hashed passwords and change-password option
- Student add, edit, delete and search
- Course management and student enrollment
- Attendance marking with percentage report
- Marks entry with results table
- Dashboard with counts, top students and low-attendance list

## How to run
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 and log in with username `admin` and password `admin123`.
Change the password after the first login.

## Tech stack
Python, Flask, Flask-SQLAlchemy, Flask-Login, SQLite, Bootstrap 5