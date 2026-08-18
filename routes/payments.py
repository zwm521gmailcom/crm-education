"""付款 / 收款记录。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Enrollment, Payment, Student

bp = Blueprint("payments", __name__)


@bp.route("/")
def list_view():
    student_id = request.args.get("student_id", type=int)
    payment_type = request.args.get("payment_type", "").strip()
    query = Payment.query
    if student_id:
        query = query.filter(Payment.student_id == student_id)
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    payments = query.order_by(Payment.paid_at.desc()).limit(500).all()
    return render_template(
        "payments/list.html",
        payments=payments,
        student_id=student_id,
        payment_type=payment_type,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        enrollment_id = request.form.get("enrollment_id", type=int) or None
        amount = _parse_decimal(request.form.get("amount"))
        if not student_id or amount <= 0:
            flash("学员和金额必填,且金额大于 0", "error")
            return _render_form(None)
        p = Payment(
            code=_gen_payment_code(),
            student_id=student_id,
            enrollment_id=enrollment_id,
            amount=amount,
            payment_type=request.form.get("payment_type", "enrollment"),
            payment_method=request.form.get("payment_method", "wechat"),
            paid_at=_parse_dt(request.form.get("paid_at")) or datetime.now(),
            notes=request.form.get("notes"),
        )
        db.session.add(p)
        db.session.commit()
        flash(f"收款已记录,收据号 {p.code}", "success")
        return redirect(url_for("payments.list_view"))
    return _render_form(None)


@bp.route("/<int:pid>/delete", methods=["POST"])
def delete(pid):
    p = Payment.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("收款记录已删除", "success")
    return redirect(url_for("payments.list_view"))


def _render_form(p):
    students = Student.query.order_by(Student.name).all()
    # 默认按学员筛报名(在 URL 里 ?student_id=xx)
    sid = request.args.get("student_id", type=int) or request.form.get("student_id", type=int)
    enrollments = []
    if sid:
        enrollments = (
            Enrollment.query.filter_by(student_id=sid, status="active")
            .order_by(Enrollment.id.desc())
            .all()
        )
    return render_template(
        "payments/form.html",
        p=p,
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


def _gen_payment_code():
    today = datetime.now().strftime("%Y%m%d")
    last = (
        Payment.query.filter(Payment.code.like(f"P{today}%"))
        .order_by(Payment.id.desc())
        .first()
    )
    if last and last.code:
        try:
            n = int(last.code[-4:]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"P{today}{n:04d}"
