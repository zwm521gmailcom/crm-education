"""退费管理。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Enrollment, Refund, Student

bp = Blueprint("refunds", __name__)


@bp.route("/")
def list_view():
    student_id = request.args.get("student_id", type=int)
    query = Refund.query
    if student_id:
        query = query.filter(Refund.student_id == student_id)
    refunds = query.order_by(Refund.refunded_at.desc()).limit(500).all()
    return render_template("refunds/list.html", refunds=refunds, student_id=student_id)


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        enrollment_id = request.form.get("enrollment_id", type=int)
        amount = _parse_decimal(request.form.get("amount"))
        if not student_id or not enrollment_id or amount <= 0:
            flash("学员、报名、金额都必填,且金额大于 0", "error")
            return _render_form(None)
        e = Enrollment.query.get(enrollment_id)
        if not e or e.student_id != student_id:
            flash("报名记录不匹配该学员", "error")
            return _render_form(None)
        r = Refund(
            code=_gen_refund_code(),
            student_id=student_id,
            enrollment_id=enrollment_id,
            amount=amount,
            reason=request.form.get("reason"),
            refund_method=request.form.get("refund_method", "original"),
            refunded_at=_parse_dt(request.form.get("refunded_at")) or datetime.now(),
            notes=request.form.get("notes"),
        )
        db.session.add(r)
        # 把报名置为已退费(如果有退费)
        e.status = "refunded"
        # 如果学员下没有其他 active 报名,把学员也置为已退费
        student = Student.query.get(student_id)
        has_active = Enrollment.query.filter(
            Enrollment.student_id == student_id, Enrollment.status == "active"
        ).count()
        if student and has_active == 0:
            student.status = "refunded"
        db.session.commit()
        flash(f"退费已记录,单号 {r.code}", "success")
        return redirect(url_for("refunds.list_view"))
    return _render_form(None)


@bp.route("/<int:rid>/delete", methods=["POST"])
def delete(rid):
    r = Refund.query.get_or_404(rid)
    e = r.enrollment
    student_id = r.student_id

    # 1) 报名回滚:该报名下没有其他退费记录 → 回滚到 active
    if e:
        other = Refund.query.filter(
            Refund.enrollment_id == e.id, Refund.id != r.id
        ).count()
        if other == 0 and e.status == "refunded":
            e.status = "active"

    # 2) 学员回滚:看学员下还有没有 active 报名,有 → 回滚到 active
    has_active = Enrollment.query.filter(
        Enrollment.student_id == student_id, Enrollment.status == "active"
    ).count()
    stu = Student.query.get(student_id)
    if stu and stu.status == "refunded" and has_active > 0:
        stu.status = "active"

    db.session.delete(r)
    db.session.commit()
    flash("退费记录已删除,关联状态已回滚", "success")
    return redirect(url_for("refunds.list_view"))


def _render_form(r):
    students = Student.query.order_by(Student.name).all()
    sid = request.args.get("student_id", type=int) or request.form.get("student_id", type=int)
    enrollments = []
    if sid:
        enrollments = (
            Enrollment.query.filter_by(student_id=sid)
            .filter(Enrollment.status.in_(("active", "completed", "refunded")))
            .order_by(Enrollment.id.desc())
            .all()
        )
    return render_template(
        "refunds/form.html",
        r=r,
        students=students,
        enrollments=enrollments,
        mode="new",
        selected_student_id=sid,
    )


def _parse_decimal(s):
    try:
        return Decimal(str(s).strip() or 0)
    except (InvalidOperation, TypeError):
        return Decimal(0)


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _gen_refund_code():
    today = datetime.now().strftime("%Y%m%d")
    last = (
        Refund.query.filter(Refund.code.like(f"R{today}%"))
        .order_by(Refund.id.desc())
        .first()
    )
    if last and last.code:
        try:
            n = int(last.code[-4:]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"R{today}{n:04d}"
