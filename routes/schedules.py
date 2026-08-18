"""课程排期与出勤(扣课时核心逻辑)。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Course, Enrollment, Schedule, ScheduleAttendance, Student

bp = Blueprint("schedules", __name__)


@bp.route("/")
def list_view():
    course_id = request.args.get("course_id", type=int)
    status = request.args.get("status", "").strip()
    range_ = request.args.get("range", "all")  # upcoming / past / all，默认全部
    view = request.args.get("view", "course")  # course / student
    student_id = request.args.get("student_id", type=int)
    attendance = request.args.get("attendance", "").strip()  # 仅学员视角生效

    courses = Course.query.filter_by(status="active").order_by(Course.name).all()
    students = Student.query.order_by(Student.name).all()

    if view == "student":
        # 学员视角:每条 (排期 × 出勤记录) 一行
        q = (
            db.session.query(Schedule, ScheduleAttendance, Enrollment, Student)
            .join(ScheduleAttendance, ScheduleAttendance.schedule_id == Schedule.id)
            .join(Enrollment, ScheduleAttendance.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
        )
        if course_id:
            q = q.filter(Schedule.course_id == course_id)
        if status:
            q = q.filter(Schedule.status == status)
        if student_id:
            q = q.filter(Student.id == student_id)
        if attendance:
            q = q.filter(ScheduleAttendance.attendance == attendance)
        if range_ == "upcoming":
            q = q.filter(Schedule.start_time >= datetime.now())
        elif range_ == "past":
            q = q.filter(Schedule.start_time < datetime.now())
        rows = q.order_by(Schedule.start_time.desc()).limit(300).all()
        return render_template(
            "schedules/list.html",
            view="student",
            rows=rows,
            courses=courses,
            students=students,
            course_id=course_id,
            student_id=student_id,
            status=status,
            attendance=attendance,
            range=range_,
        )

    # 默认课程视角
    query = Schedule.query
    if course_id:
        query = query.filter(Schedule.course_id == course_id)
    if status:
        query = query.filter(Schedule.status == status)
    if range_ == "upcoming":
        query = query.filter(Schedule.start_time >= datetime.now())
    elif range_ == "past":
        query = query.filter(Schedule.start_time < datetime.now())

    schedules = query.order_by(Schedule.start_time.desc()).limit(200).all()
    return render_template(
        "schedules/list.html",
        view="course",
        schedules=schedules,
        courses=courses,
        students=students,
        course_id=course_id,
        student_id=student_id,
        status=status,
        attendance=attendance,
        range=range_,
    )


@bp.route("/<int:sid>")
def detail(sid):
    s = Schedule.query.get_or_404(sid)
    attendances = s.attendances.order_by(ScheduleAttendance.created_at.desc()).all()
    # 候选学员:这门课的 active 报名里还有剩余课时的
    # 按 enrolled_at asc + id asc:先进先出(FIFO),最早报名优先扣课时
    candidates = (
        Enrollment.query.filter_by(course_id=s.course_id, status="active")
        .filter(Enrollment.total_hours - Enrollment.used_hours > 0)
        .order_by(Enrollment.enrolled_at.asc(), Enrollment.id.asc())
        .all()
    )
    return render_template(
        "schedules/detail.html",
        s=s,
        attendances=attendances,
        candidates=candidates,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        course = Course.query.get(course_id)
        if not course:
            flash("课程不存在", "error")
            return _render_form(None)
        start_time = _parse_dt(request.form.get("start_time"))
        end_time = _parse_dt(request.form.get("end_time"))
        if not start_time or not end_time:
            flash("开始/结束时间必填", "error")
            return _render_form(None)
        s = Schedule(
            course_id=course_id,
            teacher=request.form.get("teacher") or course.default_teacher,
            classroom=request.form.get("classroom"),
            start_time=start_time,
            end_time=end_time,
            max_students=_parse_int(request.form.get("max_students"), 1),
            hours_per_session=_parse_decimal(request.form.get("hours_per_session"), 1),
            status="scheduled",
            notes=request.form.get("notes"),
        )
        db.session.add(s)
        db.session.commit()
        flash("排期已创建", "success")
        return redirect(url_for("schedules.detail", sid=s.id))
    return _render_form(None)


@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
def edit(sid):
    s = Schedule.query.get_or_404(sid)
    if request.method == "POST":
        s.teacher = request.form.get("teacher")
        s.classroom = request.form.get("classroom")
        start_time = _parse_dt(request.form.get("start_time"))
        end_time = _parse_dt(request.form.get("end_time"))
        if start_time:
            s.start_time = start_time
        if end_time:
            s.end_time = end_time
        s.max_students = _parse_int(request.form.get("max_students"), s.max_students)
        s.hours_per_session = _parse_decimal(request.form.get("hours_per_session"), s.hours_per_session)
        s.status = request.form.get("status", s.status)
        s.notes = request.form.get("notes")
        db.session.commit()
        flash("排期已更新", "success")
        return redirect(url_for("schedules.detail", sid=s.id))
    return _render_form(s)


@bp.route("/<int:sid>/delete", methods=["POST"])
def delete(sid):
    s = Schedule.query.get_or_404(sid)
    if s.attendances.count() > 0:
        flash("该排期有出勤记录,请改状态为'已取消'", "error")
        return redirect(url_for("schedules.detail", sid=sid))
    db.session.delete(s)
    db.session.commit()
    flash("排期已删除", "success")
    return redirect(url_for("schedules.list_view"))


# ---------- 出勤 / 扣课时 ----------
@bp.route("/<int:sid>/attendance", methods=["POST"])
def add_attendance(sid):
    """添加出勤记录。出勤/补课 才会扣课时。"""
    s = Schedule.query.get_or_404(sid)
    enrollment_id = request.form.get("enrollment_id", type=int)
    attendance = request.form.get("attendance", "present")
    hours = _parse_decimal(request.form.get("hours_used"), s.hours_per_session or 1)
    notes = request.form.get("notes")

    e = Enrollment.query.get(enrollment_id)
    if not e or e.course_id != s.course_id:
        flash("报名记录与课程不匹配", "error")
        return redirect(url_for("schedules.detail", sid=sid))

    # 防重复添加
    existing = ScheduleAttendance.query.filter_by(
        schedule_id=sid, enrollment_id=enrollment_id
    ).first()
    if existing:
        flash("该学员已有出勤记录,请直接编辑", "error")
        return redirect(url_for("schedules.detail", sid=sid) + "#attendance")

    a = ScheduleAttendance(
        schedule_id=sid,
        enrollment_id=enrollment_id,
        attendance=attendance,
        hours_used=hours,
        notes=notes,
    )
    db.session.add(a)

    # 出勤/补课 扣课时
    if attendance in ("present", "makeup"):
        if e.remaining_hours < float(hours):
            db.session.rollback()
            flash(f"学员剩余课时不足(剩 {e.remaining_hours}),无法扣 {hours}", "error")
            return redirect(url_for("schedules.detail", sid=sid) + "#attendance")
        e.used_hours = (e.used_hours or 0) + float(hours)
        # 用完自动标记
        if e.remaining_hours == 0:
            e.status = "completed"
    # 请假/缺席 不扣

    db.session.commit()
    flash(f"已记录 {attendance} 状态", "success")
    return redirect(url_for("schedules.detail", sid=sid) + "#attendance")


@bp.route("/<int:sid>/attendance/<int:aid>/delete", methods=["POST"])
def delete_attendance(sid, aid):
    a = ScheduleAttendance.query.get_or_404(aid)
    if a.schedule_id != sid:
        flash("记录不匹配", "error")
        return redirect(url_for("schedules.detail", sid=sid))
    e = a.enrollment
    # 如果是扣课时的,删了要退回去
    if a.attendance in ("present", "makeup"):
        e.used_hours = max(0, (e.used_hours or 0) - float(a.hours_used))
        if e.status == "completed" and e.remaining_hours > 0:
            e.status = "active"
    db.session.delete(a)
    db.session.commit()
    flash("出勤记录已删除,课时已回退", "success")
    return redirect(url_for("schedules.detail", sid=sid) + "#attendance")


def _render_form(s):
    courses = Course.query.filter_by(status="active").order_by(Course.name).all()
    return render_template(
        "schedules/form.html",
        s=s,
        courses=courses,
        mode="edit" if s else "new",
    )


def _parse_int(s, default=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _parse_decimal(s, default=0):
    try:
        return Decimal(str(s).strip() or default)
    except (InvalidOperation, TypeError):
        return Decimal(str(default))


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None
