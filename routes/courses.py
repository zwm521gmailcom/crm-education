"""课程管理。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from extensions import db
from models import Course, Enrollment, Payment, Refund, Schedule

bp = Blueprint("courses", __name__)


@bp.route("/")
def list_view():
    q = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    status = request.args.get("status", "").strip()
    query = Course.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Course.name.like(like), Course.code.like(like)))
    if subject:
        query = query.filter(Course.subject == subject)
    if status:
        query = query.filter(Course.status == status)
    courses = query.order_by(Course.created_at.desc()).all()
    return render_template(
        "courses/list.html",
        courses=courses,
        q=q,
        subject=subject,
        status=status,
        subjects=_distinct_subjects(),
    )


@bp.route("/<int:cid>")
def detail(cid):
    course = Course.query.get_or_404(cid)
    enrollments = course.enrollments.order_by(Enrollment.enrolled_at.desc()).all()
    schedules = course.schedules.order_by(Schedule.start_time.desc()).limit(20).all()

    # 财务汇总(按本课程)
    c_total = float(
        db.session.query(func.coalesce(func.sum(Enrollment.final_price), 0))
        .filter(Enrollment.course_id == cid, Enrollment.status != "refunded")
        .scalar() or 0
    )
    c_paid = float(
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Enrollment, Payment.enrollment_id == Enrollment.id)
        .filter(Enrollment.course_id == cid)
        .scalar() or 0
    )
    c_refunded = float(
        db.session.query(func.coalesce(func.sum(Refund.amount), 0))
        .join(Enrollment, Refund.enrollment_id == Enrollment.id)
        .filter(Enrollment.course_id == cid)
        .scalar() or 0
    )
    c_unsettled = max(0.0, c_total - c_paid)
    c_student_cnt = db.session.query(func.count(func.distinct(Enrollment.student_id))).filter(
        Enrollment.course_id == cid
    ).scalar() or 0
    c_enrollment_cnt = db.session.query(func.count(Enrollment.id)).filter(
        Enrollment.course_id == cid
    ).scalar() or 0
    summary = {
        "total": c_total,
        "paid": c_paid,
        "refunded": c_refunded,
        "unsettled": c_unsettled,
        "student_cnt": int(c_student_cnt),
        "enrollment_cnt": int(c_enrollment_cnt),
    }

    return render_template(
        "courses/detail.html",
        course=course,
        enrollments=enrollments,
        schedules=schedules,
        summary=summary,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        c = Course(
            code=request.form.get("code") or _gen_course_code(),
            name=request.form.get("name", "").strip(),
            subject=request.form.get("subject"),
            grade_level=request.form.get("grade_level"),
            class_type=request.form.get("class_type", "一对一"),
            default_hours=_parse_int(request.form.get("default_hours"), 0),
            unit_price=_parse_decimal(request.form.get("unit_price"), 0),
            default_teacher=request.form.get("default_teacher"),
            description=request.form.get("description"),
            status=request.form.get("status", "active"),
        )
        if not c.name:
            flash("课程名必填", "error")
            return render_template("courses/form.html", course=c, mode="new")
        db.session.add(c)
        db.session.commit()
        flash("课程已创建", "success")
        return redirect(url_for("courses.detail", cid=c.id))
    return render_template("courses/form.html", course=None, mode="new")


@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
def edit(cid):
    course = Course.query.get_or_404(cid)
    if request.method == "POST":
        course.code = request.form.get("code") or course.code
        course.name = request.form.get("name", "").strip() or course.name
        course.subject = request.form.get("subject")
        course.grade_level = request.form.get("grade_level")
        course.class_type = request.form.get("class_type", course.class_type)
        course.default_hours = _parse_int(request.form.get("default_hours"), course.default_hours or 0)
        course.unit_price = _parse_decimal(request.form.get("unit_price"), course.unit_price or 0)
        course.default_teacher = request.form.get("default_teacher")
        course.description = request.form.get("description")
        course.status = request.form.get("status", course.status)
        db.session.commit()
        flash("课程已更新", "success")
        return redirect(url_for("courses.detail", cid=course.id))
    return render_template("courses/form.html", course=course, mode="edit")


@bp.route("/<int:cid>/delete", methods=["POST"])
def delete(cid):
    course = Course.query.get_or_404(cid)
    if course.enrollments.count() > 0:
        flash("该课程有报名记录,不能删除,可改为'下架'", "error")
        return redirect(url_for("courses.detail", cid=cid))
    db.session.delete(course)
    db.session.commit()
    flash("课程已删除", "success")
    return redirect(url_for("courses.list_view"))


# ---------- helpers ----------
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


def _distinct_subjects():
    rows = (
        db.session.query(Course.subject)
        .filter(Course.subject.isnot(None), Course.subject != "")
        .distinct()
        .all()
    )
    return sorted([r[0] for r in rows if r[0]])


def _gen_course_code():
    """C + 年月日 + 4 位序号。"""
    today = datetime.now().strftime("%Y%m%d")
    last = (
        Course.query.filter(Course.code.like(f"C{today}%"))
        .order_by(Course.id.desc())
        .first()
    )
    if last and last.code:
        try:
            n = int(last.code[-4:]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"C{today}{n:04d}"
