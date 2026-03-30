from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
db = SQLAlchemy()
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    school = db.Column(db.String(120), nullable=True)
    timetables = db.relationship("Timetable", backref="owner", lazy=True)
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile_number = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(120), nullable=True)  # Subject taught by teacher
    is_absent = db.Column(db.Boolean, default=False, nullable=False)  # Absent flag
    daily_workload = db.Column(db.Integer, default=0, nullable=False)  # Classes assigned today
    workload_date = db.Column(db.Date, default=date.today)  # Track date of workload
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    period_number = db.Column(db.Integer, nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey('period.id'), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)

class Period(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)   # "1", "2", "Break", etc
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_periods_per_teacher = db.Column(db.Integer, default=6, nullable=False)  # Max daily workload
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timetables = db.relationship("Timetable", backref="period", lazy=True, cascade="all, delete-orphan")
class SubstitutionRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    absent_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    substitute_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    timetable_id = db.Column(db.Integer, db.ForeignKey('timetable.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    period_number = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=True)  # e.g., "Absent", "Leave"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    substitute_teacher = db.relationship("Teacher", foreign_keys=[substitute_teacher_id])
class Absence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    teacher = db.relationship("Teacher")
class Substitution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    date = db.Column(db.Date)
    day = db.Column(db.String(20))

    period = db.Column(db.String(10))
    class_name = db.Column(db.String(100))

    absent_teacher = db.Column(db.String(100))
    substitute_teacher = db.Column(db.String(100))