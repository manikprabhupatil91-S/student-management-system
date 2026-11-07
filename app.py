import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from models import db, User, Student, Course, Enrollment, Attendance, Marks

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///students.db")

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------- LOGIN ----------------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    from datetime import date
    from sqlalchemy import func

    today = date.today()
    present_today = Attendance.query.filter_by(date=today, status="Present").count()
    absent_today = Attendance.query.filter_by(date=today, status="Absent").count()

    top_students = (
        db.session.query(Student, func.sum(Marks.marks).label("total"))
        .join(Marks, Marks.student_id == Student.id)
        .group_by(Student.id)
        .order_by(func.sum(Marks.marks).desc())
        .limit(3)
        .all()
    )

    low_attendance = []
    for s in Student.query.all():
        total = Attendance.query.filter_by(student_id=s.id).count()
        if total:
            present = Attendance.query.filter_by(
                student_id=s.id, status="Present"
            ).count()
            percent = round(present * 100 / total, 1)
            if percent < 75:
                low_attendance.append({"student": s, "percent": percent})
    low_attendance.sort(key=lambda x: x["percent"])

    return render_template(
        "dashboard.html",
        student_count=Student.query.count(),
        course_count=Course.query.count(),
        enrollment_count=Enrollment.query.count(),
        present_today=present_today,
        absent_today=absent_today,
        top_students=top_students,
        low_attendance=low_attendance[:5],
    )


# ---------------- STUDENTS ----------------

def read_student_form():
    year = request.form.get("year", "").strip()
    return {
        "roll_no": request.form.get("roll_no", "").strip(),
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "department": request.form.get("department", "").strip(),
        "year": int(year) if year.isdigit() else None,
    }


@app.route("/students")
@login_required
def students():
    q = request.args.get("q", "").strip()
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Student.name.ilike(like))
            | (Student.roll_no.ilike(like))
            | (Student.department.ilike(like))
        )
    all_students = query.order_by(Student.roll_no).all()
    return render_template("students.html", students=all_students, q=q)


@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        data = read_student_form()
        if not data["roll_no"] or not data["name"]:
            flash("Roll number and name are required", "danger")
        elif Student.query.filter_by(roll_no=data["roll_no"]).first():
            flash("A student with this roll number already exists", "danger")
        else:
            db.session.add(Student(**data))
            db.session.commit()
            flash("Student added successfully", "success")
            return redirect(url_for("students"))
        return render_template("student_form.html", student=data, title="Add Student")
    return render_template("student_form.html", student=None, title="Add Student")


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = db.get_or_404(Student, student_id)
    if request.method == "POST":
        data = read_student_form()
        existing = Student.query.filter_by(roll_no=data["roll_no"]).first()
        if not data["roll_no"] or not data["name"]:
            flash("Roll number and name are required", "danger")
        elif existing and existing.id != student.id:
            flash("Another student already has this roll number", "danger")
        else:
            for key, value in data.items():
                setattr(student, key, value)
            db.session.commit()
            flash("Student updated successfully", "success")
            return redirect(url_for("students"))
        return render_template("student_form.html", student=data, title="Edit Student")
    return render_template("student_form.html", student=student, title="Edit Student")


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = db.get_or_404(Student, student_id)
    Enrollment.query.filter_by(student_id=student.id).delete()
    Attendance.query.filter_by(student_id=student.id).delete()
    Marks.query.filter_by(student_id=student.id).delete()
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted", "warning")
    return redirect(url_for("students"))


# ---------------- COURSES ----------------

def read_course_form():
    credits = request.form.get("credits", "").strip()
    return {
        "course_code": request.form.get("course_code", "").strip().upper(),
        "course_name": request.form.get("course_name", "").strip(),
        "credits": int(credits) if credits.isdigit() else 3,
    }


@app.route("/courses")
@login_required
def courses():
    all_courses = Course.query.order_by(Course.course_code).all()
    counts = {
        c.id: Enrollment.query.filter_by(course_id=c.id).count()
        for c in all_courses
    }
    return render_template("courses.html", courses=all_courses, counts=counts)


@app.route("/courses/add", methods=["GET", "POST"])
@login_required
def add_course():
    if request.method == "POST":
        data = read_course_form()
        if not data["course_code"] or not data["course_name"]:
            flash("Course code and name are required", "danger")
        elif Course.query.filter_by(course_code=data["course_code"]).first():
            flash("A course with this code already exists", "danger")
        else:
            db.session.add(Course(**data))
            db.session.commit()
            flash("Course added successfully", "success")
            return redirect(url_for("courses"))
        return render_template("course_form.html", course=data, title="Add Course")
    return render_template("course_form.html", course=None, title="Add Course")


@app.route("/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    if request.method == "POST":
        data = read_course_form()
        existing = Course.query.filter_by(course_code=data["course_code"]).first()
        if not data["course_code"] or not data["course_name"]:
            flash("Course code and name are required", "danger")
        elif existing and existing.id != course.id:
            flash("Another course already has this code", "danger")
        else:
            for key, value in data.items():
                setattr(course, key, value)
            db.session.commit()
            flash("Course updated successfully", "success")
            return redirect(url_for("courses"))
        return render_template("course_form.html", course=data, title="Edit Course")
    return render_template("course_form.html", course=course, title="Edit Course")


@app.route("/courses/delete/<int:course_id>", methods=["POST"])
@login_required
def delete_course(course_id):
    course = db.get_or_404(Course, course_id)
    Enrollment.query.filter_by(course_id=course.id).delete()
    Attendance.query.filter_by(course_id=course.id).delete()
    Marks.query.filter_by(course_id=course.id).delete()
    db.session.delete(course)
    db.session.commit()
    flash("Course deleted", "warning")
    return redirect(url_for("courses"))


@app.route("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    course = db.get_or_404(Course, course_id)
    enrolled = (
        db.session.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.course_id == course.id)
        .order_by(Student.roll_no)
        .all()
    )
    enrolled_ids = [s.id for s in enrolled]
    available = (
        Student.query.filter(Student.id.notin_(enrolled_ids))
        .order_by(Student.roll_no)
        .all()
    )
    return render_template(
        "course_detail.html", course=course, enrolled=enrolled, available=available
    )


@app.route("/courses/<int:course_id>/enroll", methods=["POST"])
@login_required
def enroll_student(course_id):
    course = db.get_or_404(Course, course_id)
    student_id = request.form.get("student_id", type=int)
    if not student_id or not db.session.get(Student, student_id):
        flash("Please select a student", "danger")
    elif Enrollment.query.filter_by(student_id=student_id, course_id=course.id).first():
        flash("Student is already enrolled", "warning")
    else:
        db.session.add(Enrollment(student_id=student_id, course_id=course.id))
        db.session.commit()
        flash("Student enrolled", "success")
    return redirect(url_for("course_detail", course_id=course.id))


@app.route("/courses/<int:course_id>/unenroll/<int:student_id>", methods=["POST"])
@login_required
def unenroll_student(course_id, student_id):
    Enrollment.query.filter_by(student_id=student_id, course_id=course_id).delete()
    db.session.commit()
    flash("Student removed from course", "warning")
    return redirect(url_for("course_detail", course_id=course_id))


# ---------------- SETUP ----------------
# ---------------- ACCOUNT ----------------

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not current_user.check_password(current):
            flash("Current password is incorrect", "danger")
        elif len(new) < 8:
            flash("New password must be at least 8 characters", "danger")
        elif new != confirm:
            flash("New passwords do not match", "danger")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password changed successfully", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")
# ---------------- MARKS ----------------

EXAM_TYPES = ["Internal 1", "Internal 2", "Assignment", "Final"]
MAX_MARKS = 100


@app.route("/marks", methods=["GET", "POST"])
@login_required
def marks():
    all_courses = Course.query.order_by(Course.course_code).all()
    course_id = request.values.get("course_id", type=int)
    exam_type = request.values.get("exam_type") or EXAM_TYPES[0]
    if exam_type not in EXAM_TYPES:
        exam_type = EXAM_TYPES[0]

    course = db.session.get(Course, course_id) if course_id else None
    enrolled = []
    existing = {}

    if course:
        enrolled = get_enrolled_students(course.id)

        if request.method == "POST":
            errors = 0
            for s in enrolled:
                value = request.form.get(f"marks_{s.id}", "").strip()
                if value == "":
                    continue
                try:
                    score = float(value)
                except ValueError:
                    errors += 1
                    continue
                if score < 0 or score > MAX_MARKS:
                    errors += 1
                    continue
                record = Marks.query.filter_by(
                    student_id=s.id, course_id=course.id, exam_type=exam_type
                ).first()
                if record:
                    record.marks = score
                else:
                    db.session.add(Marks(
                        student_id=s.id,
                        course_id=course.id,
                        exam_type=exam_type,
                        marks=score,
                    ))
            db.session.commit()
            if errors:
                flash(f"{errors} invalid entries skipped (marks must be 0 to {MAX_MARKS})", "warning")
            else:
                flash("Marks saved", "success")
            return redirect(url_for(
                "marks", course_id=course.id, exam_type=exam_type
            ))

        for rec in Marks.query.filter_by(course_id=course.id, exam_type=exam_type):
            existing[rec.student_id] = rec.marks

    return render_template(
        "marks.html",
        courses=all_courses,
        course=course,
        enrolled=enrolled,
        existing=existing,
        exam_types=EXAM_TYPES,
        exam_type=exam_type,
        max_marks=MAX_MARKS,
    )


@app.route("/marks/report")
@login_required
def marks_report():
    all_courses = Course.query.order_by(Course.course_code).all()
    course_id = request.args.get("course_id", type=int)
    course = db.session.get(Course, course_id) if course_id else None
    rows = []

    if course:
        for s in get_enrolled_students(course.id):
            scores = {}
            for rec in Marks.query.filter_by(student_id=s.id, course_id=course.id):
                scores[rec.exam_type] = rec.marks
            rows.append({
                "student": s,
                "scores": scores,
                "total": sum(scores.values()),
            })

    return render_template(
        "marks_report.html",
        courses=all_courses,
        course=course,
        rows=rows,
        exam_types=EXAM_TYPES,
    )





# ---------------- ATTENDANCE ----------------

from datetime import date, datetime


def get_enrolled_students(course_id):
    return (
        db.session.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.course_id == course_id)
        .order_by(Student.roll_no)
        .all()
    )


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    all_courses = Course.query.order_by(Course.course_code).all()
    course_id = request.values.get("course_id", type=int)
    date_str = request.values.get("date") or date.today().isoformat()
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        selected_date = date.today()

    course = db.session.get(Course, course_id) if course_id else None
    enrolled = []
    existing = {}

    if course:
        enrolled = get_enrolled_students(course.id)

        if request.method == "POST":
            for s in enrolled:
                status = request.form.get(f"status_{s.id}", "Absent")
                if status not in ("Present", "Absent"):
                    status = "Absent"
                record = Attendance.query.filter_by(
                    student_id=s.id, course_id=course.id, date=selected_date
                ).first()
                if record:
                    record.status = status
                else:
                    db.session.add(Attendance(
                        student_id=s.id,
                        course_id=course.id,
                        date=selected_date,
                        status=status,
                    ))
            db.session.commit()
            flash("Attendance saved", "success")
            return redirect(url_for(
                "attendance", course_id=course.id, date=selected_date.isoformat()
            ))

        for rec in Attendance.query.filter_by(course_id=course.id, date=selected_date):
            existing[rec.student_id] = rec.status

    return render_template(
        "attendance.html",
        courses=all_courses,
        course=course,
        enrolled=enrolled,
        existing=existing,
        selected_date=selected_date.isoformat(),
    )


@app.route("/attendance/report")
@login_required
def attendance_report():
    all_courses = Course.query.order_by(Course.course_code).all()
    course_id = request.args.get("course_id", type=int)
    course = db.session.get(Course, course_id) if course_id else None
    rows = []

    if course:
        for s in get_enrolled_students(course.id):
            total = Attendance.query.filter_by(
                student_id=s.id, course_id=course.id
            ).count()
            present = Attendance.query.filter_by(
                student_id=s.id, course_id=course.id, status="Present"
            ).count()
            percent = round(present * 100 / total, 1) if total else None
            rows.append({
                "student": s,
                "total": total,
                "present": present,
                "percent": percent,
            })

    return render_template(
        "attendance_report.html", courses=all_courses, course=course, rows=rows
    )

def create_default_admin():
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(debug=True)