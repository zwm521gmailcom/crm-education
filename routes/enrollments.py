"""报名(购买课时)管理。"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import (
    Course,
    Enrollment,
    HourAdjustment,
    Payment,
    Refund,
    ScheduleAttendance,
    Student,
)

bp = Blueprint("enrollments", __name__)


@bp.route("/")
def list_view():
    status = request.args.get("status", "").strip()
    student_id = request.args.get("student_id", type=int)
    query = Enrollment.query
    if status:
        query = query.filter(Enrollment.status == status)
    if student_id:
        query = query.filter(Enrollment.student_id == student_id)
    enrollments = query.order_by(Enrollment.enrolled_at.desc()).all()
    return render_template(
        "enrollments/list.html",
        enrollments=enrollments,
        status=status,
        student_id=student_id,
    )


@bp.route("/<int:eid>")
def detail(eid):
    e = Enrollment.query.get_or_404(eid)
    attendances = e.attendances.order_by(ScheduleAttendance.created_at.desc()).all()
    payments = e.payments.order_by(Payment.paid_at.desc()).all()
    refunds = e.refunds.order_by(Refund.refunded_at.desc()).all()
    adjustments = HourAdjustment.query.filter_by(enrollment_id=eid).order_by(HourAdjustment.created_at.desc()).all()
    return render_template(
        "enrollments/detail.html",
        e=e,
        attendances=attendances,
        payments=payments,
        refunds=refunds,
        adjustments=adjustments,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        course_id = request.form.get("course_id", type=int)
        if not student_id or not course_id:
            flash("学员和课程必填", "error")
            return _render_form(None)
        student = Student.query.get(student_id)
        course = Course.query.get(course_id)
        if not student or not course:
            flash("学员或课程不存在", "error")
            return _render_form(None)

        total_hours = _parse_int(request.form.get("total_hours"), course.default_hours or 0)

        # 单价默认值:沿用该学员同课程上一次报名的单价(续费场景);
        # 没有上次记录的话用课程默认价
        last_e = (
            Enrollment.query
            .filter_by(student_id=student_id, course_id=course_id)
            .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
            .first()
        )
        default_unit = last_e.unit_price if (last_e and last_e.unit_price) else (course.unit_price or 0)
        unit_price = _parse_decimal(request.form.get("unit_price"), default_unit)

        # 价格源头:用户手动改 → manual;沿用上次 → renewal;首次或用课程默认 → default
        if last_e and Decimal(str(unit_price)) == Decimal(str(last_e.unit_price or 0)):
            price_source = "renewal"
        else:
            # 看是否跟课程默认价一致
            if Decimal(str(unit_price)) == Decimal(str(course.unit_price or 0)):
                price_source = "default"
            else:
                price_source = "manual"

        total_price = _parse_decimal(request.form.get("total_price"), total_hours * unit_price)
        discount = _parse_decimal(request.form.get("discount"), 0)
        final_price = total_price - discount
        if final_price < 0:
            discount = total_price
            final_price = Decimal(0)

        e = Enrollment(
            code=_gen_enrollment_code(),
            student_id=student_id,
            course_id=course_id,
            total_hours=total_hours,
            used_hours=0,
            unit_price=unit_price,
            total_price=total_price,
            discount=discount,
            final_price=final_price,
            price_source=price_source,
            status="active",
            enrolled_at=_parse_date(request.form.get("enrolled_at")) or datetime.now().date(),
            expires_at=_parse_date(request.form.get("expires_at")),
            notes=request.form.get("notes"),
        )
        db.session.add(e)
        db.session.commit()
        flash(f"报名成功,订单号 {e.code}", "success")
        return redirect(url_for("enrollments.detail", eid=e.id))
    return _render_form(None)


@bp.route("/<int:eid>/edit", methods=["GET", "POST"])
def edit(eid):
    e = Enrollment.query.get_or_404(eid)
    if request.method == "POST":
        e.total_hours = _parse_int(request.form.get("total_hours"), e.total_hours)
        e.unit_price = _parse_decimal(request.form.get("unit_price"), e.unit_price)
        e.total_price = _parse_decimal(request.form.get("total_price"), e.total_price)
        e.discount = _parse_decimal(request.form.get("discount"), e.discount)
        e.final_price = e.total_price - e.discount
        if request.form.get("enrolled_at"):
            e.enrolled_at = _parse_date(request.form.get("enrolled_at"))
        e.expires_at = _parse_date(request.form.get("expires_at"))
        e.status = request.form.get("status", e.status)
        e.notes = request.form.get("notes")
        db.session.commit()
        flash("报名信息已更新", "success")
        return redirect(url_for("enrollments.detail", eid=e.id))
    return _render_form(e)


@bp.route("/<int:eid>/delete", methods=["POST"])
def delete(eid):
    e = Enrollment.query.get_or_404(eid)
    if e.payments.count() > 0 or e.attendances.count() > 0 or e.refunds.count() > 0:
        flash("该报名有相关流水,不能直接删除,可改为'已退费'状态", "error")
        return redirect(url_for("enrollments.detail", eid=eid))
    db.session.delete(e)
    db.session.commit()
    flash("报名已删除", "success")
    return redirect(url_for("enrollments.list_view"))


# ---------- 课时调整流水 ----------
@bp.route("/<int:eid>/adjustments", methods=["POST"])
def add_adjustment(eid):
    """手工调整课时(+ 赠送/- 扣减),同时更新 enrollment.total_hours。"""
    e = Enrollment.query.get_or_404(eid)
    try:
        change = float(request.form.get("change_hours", 0))
    except (TypeError, ValueError):
        change = 0
    if change == 0:
        flash("调整课时不能为 0", "error")
        return redirect(url_for("enrollments.detail", eid=eid) + "#adjustments")
    reason = request.form.get("reason", "").strip() or "未填写"
    operator = request.form.get("operator", "").strip() or None

    # 调整:加到 total_hours(正数 = 赠送,负数 = 扣减)
    new_total = (e.total_hours or 0) + change
    if new_total < (e.used_hours or 0):
        db.session.rollback()
        flash(f"调整后总课时({new_total})小于已用课时({e.used_hours}),无法扣减", "error")
        return redirect(url_for("enrollments.detail", eid=eid) + "#adjustments")

    a = HourAdjustment(
        enrollment_id=eid,
        change_hours=change,
        reason=reason,
        operator=operator,
    )
    e.total_hours = new_total
    # 如果因为赠送让 remaining > 0,把 completed 状态回滚成 active
    if e.status == "completed" and e.remaining_hours > 0:
        e.status = "active"
    db.session.add(a)
    db.session.commit()
    flash(f"已{'赠送' if change > 0 else '扣减'} {abs(change)} 课时", "success")
    return redirect(url_for("enrollments.detail", eid=eid) + "#adjustments")


def _render_form(e):
    students = Student.query.filter(Student.status.in_(("active", "suspended"))).order_by(Student.name).all()
    courses = Course.query.filter_by(status="active").order_by(Course.name).all()
    return render_template(
        "enrollments/form.html",
        e=e,
        students=students,
        courses=courses,
        mode="edit" if e else "new",
    )


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


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _gen_enrollment_code():
    today = datetime.now().strftime("%Y%m%d")
    last = (
        Enrollment.query.filter(Enrollment.code.like(f"E{today}%"))
        .order_by(Enrollment.id.desc())
        .first()
    )
    if last and last.code:
        try:
            n = int(last.code[-4:]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"E{today}{n:04d}"
