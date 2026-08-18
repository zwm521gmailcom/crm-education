"""仪表盘:核心指标。"""
import calendar
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, render_template
from sqlalchemy import func

from extensions import db
from models import (
    Student,
    Course,
    Enrollment,
    Schedule,
    ScheduleAttendance,
    Payment,
    Refund,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
def index():
    # ---- 学员指标 ----
    student_total = Student.query.count()
    student_active = Student.query.filter_by(status="active").count()
    student_refunded = Student.query.filter_by(status="refunded").count()

    # ---- 课程指标 ----
    course_active = Course.query.filter_by(status="active").count()

    # ---- 课时指标 ----
    total_hours = (
        db.session.query(func.coalesce(func.sum(Enrollment.total_hours), 0))
        .filter(Enrollment.status == "active")
        .scalar()
    ) or 0
    used_hours = (
        db.session.query(func.coalesce(func.sum(Enrollment.used_hours), 0))
        .filter(Enrollment.status == "active")
        .scalar()
    ) or 0
    remaining_hours = (total_hours or 0) - (used_hours or 0)

    # ---- 营收 ----
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    next_month_start = month_start.replace(day=last_day) + timedelta(days=1)
    revenue_month = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.paid_at >= month_start)
        .scalar()
    ) or Decimal(0)
    revenue_total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar()
    ) or Decimal(0)
    refund_month = (
        db.session.query(func.coalesce(func.sum(Refund.amount), 0))
        .filter(Refund.refunded_at >= month_start)
        .scalar()
    ) or Decimal(0)
    refund_total = (
        db.session.query(func.coalesce(func.sum(Refund.amount), 0)).scalar()
    ) or Decimal(0)

    # ---- 已消耗金额 = SUM(used_hours × unit_price),排除已退费 ----
    used_value_total = (
        db.session.query(
            func.coalesce(func.sum(Enrollment.used_hours * Enrollment.unit_price), 0)
        )
        .filter(Enrollment.status != "refunded")
        .scalar()
    ) or Decimal(0)

    # ---- 本月排期消耗 = Σ(本月排期 attendance.hours_used × enrollment.unit_price) ----
    # 只算扣课的出勤/补课,且 hours_used > 0
    month_used_hours = (
        db.session.query(
            func.coalesce(func.sum(ScheduleAttendance.hours_used), 0)
        )
        .join(Schedule, ScheduleAttendance.schedule_id == Schedule.id)
        .filter(Schedule.start_time >= month_start)
        .filter(Schedule.start_time < next_month_start)
        .filter(ScheduleAttendance.attendance.in_(("present", "makeup")))
        .filter(ScheduleAttendance.hours_used > 0)
        .scalar()
    ) or 0
    month_used_value = (
        db.session.query(
            func.coalesce(
                func.sum(ScheduleAttendance.hours_used * Enrollment.unit_price), 0
            )
        )
        .join(Schedule, ScheduleAttendance.schedule_id == Schedule.id)
        .join(Enrollment, ScheduleAttendance.enrollment_id == Enrollment.id)
        .filter(Schedule.start_time >= month_start)
        .filter(Schedule.start_time < next_month_start)
        .filter(ScheduleAttendance.attendance.in_(("present", "makeup")))
        .filter(ScheduleAttendance.hours_used > 0)
        .scalar()
    ) or Decimal(0)

    # ---- 未来一周排期 ----
    now = datetime.now()
    upcoming = (
        Schedule.query.filter(Schedule.start_time >= now, Schedule.status == "scheduled")
        .order_by(Schedule.start_time.asc())
        .limit(8)
        .all()
    )

    # ---- 课时紧张学员(剩余 <=3) ----
    tight_hours = (
        Enrollment.query.filter(Enrollment.status == "active")
        .filter(Enrollment.total_hours - Enrollment.used_hours <= 3)
        .order_by((Enrollment.total_hours - Enrollment.used_hours).asc())
        .limit(8)
        .all()
    )

    # ---- 退费明细:已退费学员 + 最近退费记录 ----
    # 已退费学员:每位总退费额、笔数、最近一次退费时间(按最近一次退费倒序)
    refunded_students_rows = db.session.execute(db.text("""
        SELECT s.id AS sid, s.name AS sname, s.code AS scode,
               COUNT(r.id) AS cnt, COALESCE(SUM(r.amount), 0) AS total,
               MAX(r.refunded_at) AS last_at
        FROM students s
        JOIN refunds r ON r.student_id = s.id
        GROUP BY s.id
        ORDER BY last_at DESC
        LIMIT 8
    """)).fetchall()
    refunded_students = [
        {
            "student": Student.query.get(r.sid),
            "refund_count": r.cnt,
            "refund_total": float(r.total),
            # raw SQL 的 MAX(refunded_at) 是 str,转成 datetime 才能过 dt filter
            "last_refund_at": datetime.fromisoformat(r.last_at) if r.last_at else None,
        }
        for r in refunded_students_rows
    ]

    # 最近退费记录:含学员/报名/课程(joinedload 避免 N+1)
    from sqlalchemy.orm import joinedload
    recent_refunds = (
        Refund.query
        .options(
            joinedload(Refund.student),
            joinedload(Refund.enrollment).joinedload(Enrollment.course),
        )
        .order_by(Refund.refunded_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard.html",
        student_total=student_total,
        student_active=student_active,
        student_refunded=student_refunded,
        course_active=course_active,
        total_hours=total_hours,
        used_hours=used_hours,
        remaining_hours=remaining_hours,
        revenue_month=revenue_month,
        revenue_total=revenue_total,
        refund_month=refund_month,
        refund_total=refund_total,
        used_value_total=used_value_total,
        month_used_value=month_used_value,
        month_used_hours=month_used_hours,
        upcoming=upcoming,
        tight_hours=tight_hours,
        refunded_students=refunded_students,
        recent_refunds=recent_refunds,
    )
