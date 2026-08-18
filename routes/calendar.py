"""排期日历视图:周视图 + 月视图,支持课程/学员两种角度。"""
import calendar as _cal
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request

from extensions import db
from models import (
    Course,
    Enrollment,
    Schedule,
    ScheduleAttendance,
    Student,
)

bp = Blueprint("calendar", __name__)


def _parse_date(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


@bp.route("/calendar", strict_slashes=False)
def view():
    """日历视图入口。通过 ?view=week|month + ?angle=course|student 切换。"""
    view_mode = request.args.get("view", "week")
    angle = request.args.get("angle", "course")  # course / student
    if view_mode == "month":
        return _month_view(angle)
    return _week_view(angle)


# ==================== 共享查询 ====================
def _query_schedules(start_d, end_d, course_id, teacher):
    """课程视角:返回 Schedule 列表(按开始时间升序)。"""
    q = Schedule.query.filter(
        Schedule.start_time >= datetime.combine(start_d, datetime.min.time()),
        Schedule.start_time <= datetime.combine(end_d, datetime.max.time()),
    )
    if course_id:
        q = q.filter(Schedule.course_id == course_id)
    if teacher:
        q = q.filter(Schedule.teacher == teacher)
    return q.order_by(Schedule.start_time.asc()).all()


def _query_attendances(start_d, end_d, course_id, teacher, student_id, attendance):
    """学员视角:返回 (Schedule, ScheduleAttendance, Enrollment, Student) 行。"""
    q = (
        db.session.query(Schedule, ScheduleAttendance, Enrollment, Student)
        .join(ScheduleAttendance, ScheduleAttendance.schedule_id == Schedule.id)
        .join(Enrollment, ScheduleAttendance.enrollment_id == Enrollment.id)
        .join(Student, Enrollment.student_id == Student.id)
        .filter(
            Schedule.start_time >= datetime.combine(start_d, datetime.min.time()),
            Schedule.start_time <= datetime.combine(end_d, datetime.max.time()),
        )
    )
    if course_id:
        q = q.filter(Schedule.course_id == course_id)
    if teacher:
        q = q.filter(Schedule.teacher == teacher)
    if student_id:
        q = q.filter(Student.id == student_id)
    if attendance:
        q = q.filter(ScheduleAttendance.attendance == attendance)
    return q.order_by(Schedule.start_time.asc()).all()


def _get_courses_and_teachers():
    courses = Course.query.filter_by(status="active").order_by(Course.name).all()
    teachers = [
        r[0]
        for r in db.session.query(Schedule.teacher)
        .filter(Schedule.teacher.isnot(None), Schedule.teacher != "")
        .distinct()
        .all()
        if r[0]
    ]
    teachers = sorted(teachers)
    return courses, teachers


def _get_students():
    return Student.query.order_by(Student.name).all()


# ==================== 周视图 ====================
def _week_view(angle):
    today = datetime.now().date()
    default_monday = today - timedelta(days=today.weekday())
    week_start = _parse_date(request.args.get("week"), default_monday)
    week_start = week_start - timedelta(days=week_start.weekday())
    week_end = week_start + timedelta(days=6)

    course_id = request.args.get("course_id", type=int)
    teacher = request.args.get("teacher", "").strip()
    student_id = request.args.get("student_id", type=int)
    attendance = request.args.get("attendance", "").strip()

    days = [week_start + timedelta(days=i) for i in range(7)]
    courses, teachers = _get_courses_and_teachers()

    if angle == "student":
        rows = _query_attendances(week_start, week_end, course_id, teacher, student_id, attendance)
        # 按日期分组
        by_day = {d: [] for d in days}
        for s, a, e, st in rows:
            day = s.start_time.date()
            if day in by_day:
                by_day[day].append((s, a, e, st))
        return render_template(
            "schedules/calendar.html",
            angle="student",
            view_mode="week",
            week_start=week_start,
            week_end=week_end,
            prev_week=week_start - timedelta(days=7),
            next_week=week_start + timedelta(days=7),
            today=today,
            days=days,
            by_day=by_day,
            courses=courses,
            teachers=teachers,
            students=_get_students(),
            course_id=course_id,
            teacher=teacher,
            student_id=student_id,
            attendance=attendance,
        )

    # course angle (default)
    schedules = _query_schedules(week_start, week_end, course_id, teacher)
    by_day = {d: [] for d in days}
    for s in schedules:
        day = s.start_time.date()
        if day in by_day:
            by_day[day].append(s)

    return render_template(
        "schedules/calendar.html",
        angle="course",
        view_mode="week",
        week_start=week_start,
        week_end=week_end,
        prev_week=week_start - timedelta(days=7),
        next_week=week_start + timedelta(days=7),
        today=today,
        days=days,
        by_day=by_day,
        courses=courses,
        teachers=teachers,
        students=_get_students(),
        course_id=course_id,
        teacher=teacher,
    )


# ==================== 月视图 ====================
def _month_view(angle):
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    course_id = request.args.get("course_id", type=int)
    teacher = request.args.get("teacher", "").strip()
    student_id = request.args.get("student_id", type=int)
    attendance = request.args.get("attendance", "").strip()

    first = date(year, month, 1)
    last_day_num = _cal.monthrange(year, month)[1]
    last = date(year, month, last_day_num)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())
    days = [grid_start + timedelta(days=i) for i in range((grid_end - grid_start).days + 1)]

    courses, teachers = _get_courses_and_teachers()

    if angle == "student":
        rows = _query_attendances(grid_start, grid_end, course_id, teacher, student_id, attendance)
        by_day = {d: [] for d in days}
        for s, a, e, st in rows:
            d_ = s.start_time.date()
            if d_ in by_day:
                by_day[d_].append((s, a, e, st))
    else:
        schedules = _query_schedules(grid_start, grid_end, course_id, teacher)
        by_day = {d: [] for d in days}
        for s in schedules:
            d_ = s.start_time.date()
            if d_ in by_day:
                by_day[d_].append(s)

    if month == 1:
        prev_y, prev_m = year - 1, 12
    else:
        prev_y, prev_m = year, month - 1
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1

    return render_template(
        "schedules/calendar_month.html",
        angle=angle,
        view_mode="month",
        today=today,
        year=year,
        month=month,
        month_label=f"{year} 年 {month} 月",
        grid_start=grid_start,
        grid_end=grid_end,
        days=days,
        by_day=by_day,
        first=first,
        last=last,
        prev_y=prev_y,
        prev_m=prev_m,
        next_y=next_y,
        next_m=next_m,
        courses=courses,
        teachers=teachers,
        students=_get_students(),
        course_id=course_id,
        teacher=teacher,
        student_id=student_id,
        attendance=attendance,
    )
