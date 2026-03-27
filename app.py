from collections import defaultdict
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for,flash,abort
from flask_login import LoginManager,login_user,logout_user,login_required,current_user
from werkzeug.security import generate_password_hash,check_password_hash
from config import Config
from models import Absence, Substitution, db, User, Timetable, Teacher, Period 
import csv
import statistics
import os
app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
app.config.from_object(Config)
db.init_app(app)
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        school = request.form["school"]
        username = request.form["username"]
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Username already taken", "danger")
            return redirect(url_for("register"))
        new_user = User(email=email, password_hash=generate_password_hash(password), username=username, school=school)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash("Account created successfully", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")
@app.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow() + timedelta(hours=5)  # Pakistan time

    today = now.date()
    current_time = now.time()
    day = now.strftime("%A")

    # ---- Fetch data ----
    teachers = Teacher.query.filter_by(user_id=current_user.id).all()
    periods = Period.query.filter_by(user_id=current_user.id).order_by(Period.start_time).all()

    timetable = Timetable.query.filter_by(
        user_id=current_user.id,
        day=day
    ).all()

    absentees = Absence.query.filter_by(
        user_id=current_user.id,
        date=today
    ).all()

    substitutions = Substitution.query.filter_by(
        user_id=current_user.id,
        date=today
    ).all()

    # ---- Analytics ----
    total_teachers = len(teachers)
    absentees_count = len(absentees)
    substitutions_count = len(substitutions)
    total_classes = len(set([t.class_name for t in timetable]))

    # ---- FIND CURRENT PERIOD ----
    current_period = None
    for p in periods:
        if p.start_time <= current_time < p.end_time:
            current_period = p
            break

    # ---- CURRENT PERIOD CLASSES ----
    current_classes = []

    if current_period:
        current_period_number = current_period.id

        for t in timetable:
            if str(t.period_number) == current_period.name.replace("Period ", ""):

                # check substitution
                sub = Substitution.query.filter_by(
                    user_id=current_user.id,
                    date=today,
                    period=str(t.period_number),
                    class_name=t.class_name
                ).first()

                teacher_name = t.teacher.name
                status = "Normal"
                absent_teacher = None

                # check if teacher absent
                is_absent = any(a.teacher_id == t.teacher_id for a in absentees)

                if is_absent:
                    status = "Absent"

                if sub:
                    status = "Substituted"
                    absent_teacher = sub.absent_teacher
                    teacher_name = sub.substitute_teacher

                current_classes.append({
                    "class_name": t.class_name,
                    "subject": t.subject,
                    "teacher": teacher_name,
                    "status": status,
                    "absent_teacher": absent_teacher
                })
    else:
        current_period_number = None

    # ---- TODAY'S PERIOD COUNT ----
    today_periods = Timetable.query.filter_by(
        user_id=current_user.id,
        day=day
    ).all()

    # ---- WORKLOAD (INCLUDING SUBSTITUTIONS) ----
    # Get list of absent teacher names
    absent_teacher_ids = [a.teacher_id for a in absentees]
    
    workload = {}

# Initialize ALL present teachers with 0
    for teacher in teachers:
        if teacher.id not in absent_teacher_ids:
            workload[teacher.name] = 0

    # Count timetable periods
    for t in today_periods:
        if t.teacher_id not in absent_teacher_ids:
            teacher_name = t.teacher.name
            workload[teacher_name] += 1

    # Add substitutions
    for sub in substitutions:
        teacher = Teacher.query.filter_by(
            name=sub.substitute_teacher,
            user_id=current_user.id
        ).first()

        if teacher and teacher.id not in absent_teacher_ids:
            workload[sub.substitute_teacher] += 1

    # ---- CHART DATA ----
    teacher_labels = list(workload.keys())
    teacher_values = list(workload.values())
    teacherdata = list(zip(teacher_labels, teacher_values))

    # ---- FAIRNESS CALCULATION (EXCLUDING ABSENT TEACHERS) ----
    values = list(workload.values())

    if values and len(values) > 1:
        avg = sum(values) / len(values)
        variance = statistics.pvariance(values)

        # fairness score (simple normalized metric)
        fairness_score = max(0, 100 - (variance * 10))
        fairness_score = round(fairness_score, 2)
    else:
        fairness_score = 100

    return render_template(
        "dashboard.html",
        current_period=current_period_number,
        current_period_obj=current_period,
        current_classes=current_classes,
        total_teachers=total_teachers,
        absentees_count=absentees_count,
        substitutions_count=substitutions_count,
        total_classes=total_classes,
        teacher_labels=teacher_labels,
        teacher_values=teacher_values,
        fairness_score=fairness_score,
        teacherdata=teacherdata,
        absent_teacher_ids=absent_teacher_ids
    )
def validate_csv(file, expected_columns):
    """Validate CSV columns"""
    try:
        stream = file.stream.read().decode("utf-8").splitlines()
        reader = csv.reader(stream)
        header = next(reader)
        if header != expected_columns:
            return False
        return True
    except Exception as e:
        print(e)
        return False

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    # Clear old data before uploading new CSV
    Timetable.query.filter_by(user_id=current_user.id).delete()
    Absence.query.filter_by(user_id=current_user.id).delete()
    Substitution.query.filter_by(user_id=current_user.id).delete()
    Teacher.query.filter_by(user_id=current_user.id).delete()


    if request.method == "POST":

        teacher_file_format = ["Teacher", "Mobile Number"]
        timetable_format = ["Period Number", "Teacher", "Subject", "Day","Class Name"]

        timetable_file = request.files.get("timetable_file")
        teacher_file = request.files.get("teacher_file")

        if not timetable_file or not teacher_file:
            flash("Please upload both files", "danger")
            return redirect(url_for("upload"))

        if not validate_csv(timetable_file, timetable_format) or not validate_csv(teacher_file, teacher_file_format):
            flash("File format is incorrect", "danger")
            return redirect(url_for("upload"))
        teacher_file.seek(0)
        teacher_reader = csv.DictReader(teacher_file.read().decode("utf-8").splitlines())

        teacher_map = {}

                # 1️⃣ Normalize headers (case-insensitive + spaces → underscores)
        normalized_headers = {h.lower().replace(" ", "_"): h for h in teacher_reader.fieldnames}

        for row in teacher_reader:
            teacher_name = row.get(normalized_headers.get("teacher"), "").strip()
            mobile_number = row.get(normalized_headers.get("mobile_number"), "").strip()

            if not teacher_name:
                continue  # skip rows with no teacher name

            teacher = Teacher.query.filter_by(
                name=teacher_name,
                user_id=current_user.id
            ).first()

            if not teacher:
                teacher = Teacher(
                    name=teacher_name,
                    mobile_number=mobile_number,
                    user_id=current_user.id
                )
                db.session.add(teacher)
                db.session.flush()

            teacher_map[teacher_name] = teacher.id

        timetable_file.seek(0)
        timetable_reader = csv.DictReader(timetable_file.read().decode("utf-8").splitlines())
        normalized_headers_t = {h.lower().replace(" ", "_"): h for h in timetable_reader.fieldnames}
        missing_periods = []
        
        for row in timetable_reader:
            period_number_str = row[normalized_headers_t["period_number"]].strip()
            period_number_int = int(period_number_str)

            # find the Period object in DB
            period = Period.query.filter_by(
                user_id=current_user.id,
                name= f"Period {period_number_str}"  # match your Period.name with CSV Period Number
            ).first()

            if not period:
                missing_periods.append(period_number_str)
                continue  # skip this row if Period not found

            t = Timetable(
                user_id=current_user.id,
                teacher_id=teacher_map[row[normalized_headers_t["teacher"]]],
                subject=row[normalized_headers_t["subject"]],
                day=row[normalized_headers_t["day"]],
                period_number=period_number_int,
                period_id=period.id,  # ⚡ assign the foreign key here
                class_name=row[normalized_headers_t["class_name"]]
            )
            db.session.add(t)

        db.session.commit()

        if missing_periods:
            flash(f"⚠️ Periods NOT found: {', '.join(missing_periods)}. Create these periods first!", "danger")
        else:
            flash("Timetable Added successfully ✅", "success")
        return redirect(url_for("dashboard"))
    return render_template("upload.html")
@app.route("/periods", methods=["GET", "POST"])
@login_required
def periods():
    if request.method == "POST":
        start = datetime.strptime(request.form.get("start_time"), "%H:%M").time()
        end = datetime.strptime(request.form.get("end_time"), "%H:%M").time()

        period_count = Period.query.filter_by(user_id=current_user.id).count()
        period_number = period_count +1

        period = Period(
            name= f"Period {period_number}",
            start_time=start,
            end_time=end,
            user_id=current_user.id
        )
        db.session.add(period)
        db.session.commit()

        flash("Period added", "success")
        return redirect(url_for("periods"))

    user_periods = Period.query.filter_by(user_id=current_user.id).order_by(Period.start_time).all()
    return render_template("periods.html", periods=user_periods)
@app.route("/period/delete/<int:id>",methods=["POST"])
@login_required
def delete_period(id):
    period = Period.query.get_or_404(id)

    if period.user_id != current_user.id:
        abort(403)

    db.session.delete(period)
    db.session.commit()

    flash("Period deleted", "success")
    return redirect(url_for("periods"))

@app.route("/assign_substitute")
@login_required
def assign_substitute():
    today = date.today()
    day = today.strftime("%A")
    all_teachers = Teacher.query.filter_by(user_id=current_user.id).all()
    
    # Reset workload if new day
    for teacher in all_teachers:
        if teacher.workload_date != today:
            teacher.daily_workload = 0
            teacher.workload_date = today
    
    db.session.commit()
    
    # Delete old substitutions and get fresh data
    Substitution.query.filter_by(
        user_id=current_user.id,
        date=today
    ).delete()
    db.session.commit()
    
    day = today.strftime("%A")
    
    # Get absent teachers
    absences = Absence.query.filter_by(
        date=today,
        user_id=current_user.id
    ).all()
    
    absent_teacher_ids = [a.teacher_id for a in absences]
    
    if not absent_teacher_ids:
        flash("No absent teachers today", "warning")
        return redirect(url_for("absent_today"))
    
    # Recalculate workload from scratch
    all_teachers = Teacher.query.filter_by(user_id=current_user.id).all()
    teacher_load = {t.id: 0 for t in all_teachers}
    temp_workload = {t.id: 0 for t in all_teachers}
    
    # Count current timetable assignments
    today_periods = Timetable.query.filter_by(
        user_id=current_user.id,
        day=day
    ).all()
    
    for t in today_periods:
        if t.teacher_id in teacher_load:
            teacher_load[t.teacher_id] += 1
    
    results = []
    
    # Loop each absent teacher
    for absent_id in absent_teacher_ids:
        timetables = Timetable.query.filter_by(
            teacher_id=absent_id,
            day=day,
            user_id=current_user.id
        ).all()
        
        for t in timetables:
            # Get available teachers (exclude absent teachers)
            available_teachers = [
                teacher for teacher in all_teachers
                if teacher.id not in absent_teacher_ids
            ]
            
            # Remove teachers already teaching at THIS period
            busy_teacher_ids = [
                row.teacher_id
                for row in today_periods
                if row.period_number == t.period_number
            ]
            
            available_teachers = [
                teacher for teacher in available_teachers
                if teacher.id not in busy_teacher_ids
            ]
            
            # If no one available
            if not available_teachers:
                sub = Substitution(
                    user_id=current_user.id,
                    date=today,
                    day=day,
                    period=str(t.period_number),
                    class_name=t.class_name,
                    absent_teacher=db.session.get(Teacher, absent_id).name,
                    substitute_teacher="No teacher available"
                )
                db.session.add(sub)
                results.append({
                    "class": t.class_name,
                    "period": t.period_number,
                    "substitute": "No teacher available",
                    "absent_teacher": db.session.get(Teacher, absent_id).name
                })
                continue
            
            # Sort by workload (ascending)
            available_teachers.sort(
                key=lambda x: (
                    teacher_load.get(x.id, 0) + temp_workload.get(x.id, 0),
                    x.daily_workload
                )
            )
            
            # Assign the teacher with lowest workload
            substitute = available_teachers[0]
            substitute.daily_workload += 1
            temp_workload[substitute.id] += 1
            
            # Save substitution
            sub = Substitution(
                user_id=current_user.id,
                date=today,
                day=day,
                period=str(t.period_number),
                class_name=t.class_name,
                absent_teacher=db.session.get(Teacher, absent_id).name,
                substitute_teacher=substitute.name
            )
            db.session.add(sub)
            results.append({
                "class": t.class_name,
                "period": t.period_number,
                "substitute": substitute.name,
                "absent_teacher": db.session.get(Teacher, absent_id).name
            })
    
    db.session.commit()
    
    if results:
        flash(f"Substitutes assigned successfully! {len(results)} assignments.", "success")
    else:
        flash("No substitutes needed or could be assigned", "info")
    
    return render_template(
        "absent_today.html",
        absentees=Absence.query.filter_by(date=today, user_id=current_user.id).all(),
        results=Substitution.query.filter_by(user_id=current_user.id, date=today).all()
    )

@app.route('/teachers_page')
@login_required
def teachers_page():
    today = date.today()

    teachers = Teacher.query.filter_by(user_id=current_user.id).all()

    absences = Absence.query.filter_by(
        date=today,
        user_id=current_user.id
    ).all()

    absent_ids = [a.teacher_id for a in absences]

    return render_template(
        "teachers.html",
        teachers=teachers,
        absent_ids=absent_ids
    )

@app.route("/mark_absent/<int:teacher_id>")
@login_required
def mark_absent(teacher_id):
    today = date.today()

    existing = Absence.query.filter_by(
        teacher_id=teacher_id,
        date=today,
        user_id=current_user.id
    ).first()

    if not existing:
        absence = Absence(
            teacher_id=teacher_id,
            date=today,
            user_id=current_user.id
        )
        db.session.add(absence)
        db.session.commit()

    flash("Teacher marked absent for today", "success")
    return redirect(url_for("teachers_page"))
@app.route("/absent_today")
@login_required
def absent_today():
    today = date.today()
    day = today.strftime("%A")

    absentees = Absence.query.filter_by(
        date=today,
        user_id=current_user.id
    ).all()

    results = Substitution.query.filter_by(
        user_id=current_user.id,date = today
    ).all()

    return render_template(
        "absent_today.html",
        absentees=absentees,
        results=results
    )

@app.route("/undo_absent/<int:teacher_id>")
@login_required
def undo_absent(teacher_id):
    today = date.today()

    absence = Absence.query.filter_by(
        teacher_id=teacher_id,
        date=today,
        user_id=current_user.id
    ).first()

    if absence:
        db.session.delete(absence)
        db.session.commit()
        flash("Absence removed ✅", "success")

    return redirect(url_for("teachers_page"))