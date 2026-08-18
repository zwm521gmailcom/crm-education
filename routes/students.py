"""学生与联系人。"""
import calendar as _cal
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from extensions import db
from models import (
    Contact,
    Enrollment,
    Payment,
    Refund,
    Schedule,
    ScheduleAttendance,
    Student,
)

bp = Blueprint("students", __name__)

# 学员列表可排序列(供 list_view + exports 复用)
STUDENT_SORT_KEYS = (
    "code", "name", "school", "status",
    "remaining_hours", "used_value",
    "enrollment_date", "created_at",
)


def _student_sort_subqueries():
    """返回 (剩余课时子查询, 已用金额子查询),供排序用。
    剩余课时用 status='active'(与 Student.total_remaining_hours 一致),
    已用金额用 status != 'refunded'(与学员汇总卡一致)。"""
    rem_subq = (
        db.session.query(
            Enrollment.student_id.label("sid"),
            func.coalesce(
                func.sum(Enrollment.total_hours - Enrollment.used_hours), 0
            ).label("remaining"),
        )
        .filter(Enrollment.status == "active")
        .group_by(Enrollment.student_id)
        .subquery()
    )
    uv_subq = (
        db.session.query(
            Enrollment.student_id.label("sid2"),
            func.coalesce(
                func.sum(Enrollment.used_hours * Enrollment.unit_price), 0
            ).label("used_value"),
        )
        .filter(Enrollment.status != "refunded")
        .group_by(Enrollment.student_id)
        .subquery()
    )
    return rem_subq, uv_subq


def _apply_student_sort(query, sort, direction):
    """按 sort/dir 套 ORDER BY,默认 created_at desc。返回 (query, sort_col_obj)。"""
    rem_subq, uv_subq = _student_sort_subqueries()
    query = query.outerjoin(rem_subq, rem_subq.c.sid == Student.id)
    query = query.outerjoin(uv_subq, uv_subq.c.sid2 == Student.id)

    remaining_expr = func.coalesce(rem_subq.c.remaining, 0)
    used_value_expr = func.coalesce(uv_subq.c.used_value, 0)

    col_map = {
        "code": Student.code,
        "name": Student.name,
        "school": Student.school,
        "status": Student.status,
        "remaining_hours": remaining_expr,
        "used_value": used_value_expr,
        "enrollment_date": Student.enrollment_date,
        "created_at": Student.created_at,
    }
    col = col_map.get(sort, Student.created_at)
    is_asc = (direction == "asc")
    if is_asc:
        query = query.order_by(col.asc(), Student.id.asc())
    else:
        query = query.order_by(col.desc(), Student.id.desc())
    return query


@bp.route("/")
def list_view():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "created_at")
    if sort not in STUDENT_SORT_KEYS:
        sort = "created_at"
    direction = request.args.get("dir", "desc")
    if direction not in ("asc", "desc"):
        direction = "desc"

    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Student.name.like(like),
                Student.code.like(like),
                Student.phone.like(like),
                Student.school.like(like),
            )
        )
    if status:
        query = query.filter(Student.status == status)
    query = _apply_student_sort(query, sort, direction)
    students = query.all()

    # 学员已用课时金额(模板里渲染用)
    used_value_rows = (
        db.session.query(
            Enrollment.student_id,
            func.coalesce(func.sum(Enrollment.used_hours * Enrollment.unit_price), 0),
        )
        .filter(Enrollment.status != "refunded")
        .group_by(Enrollment.student_id)
        .all()
    )
    used_value_map = {sid: float(v) for sid, v in used_value_rows}

    return render_template(
        "students/list.html",
        students=students,
        q=q,
        status=status,
        sort=sort,
        direction=direction,
        used_value_map=used_value_map,
    )


def _build_student_calendar(sid, year, month):
    """构建学员视角的月度日历数据。

    返回:
        days: [{date, in_month, is_today, attendances: [(schedule, attendance, enrollment), ...]}, ...]
        month_label: "2026 年 8 月"
        prev_y, prev_m, next_y, next_m: 翻页用
        totals: {sessions, present, makeup, absent, leave, hours, value, value_count}
    """
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    first = date(year, month, 1)
    last_day_num = _cal.monthrange(year, month)[1]
    last = date(year, month, last_day_num)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())

    rows = (
        db.session.query(Schedule, ScheduleAttendance, Enrollment)
        .join(ScheduleAttendance, ScheduleAttendance.schedule_id == Schedule.id)
        .join(Enrollment, ScheduleAttendance.enrollment_id == Enrollment.id)
        .filter(Enrollment.student_id == sid)
        .filter(Schedule.start_time >= datetime.combine(grid_start, datetime.min.time()))
        .filter(Schedule.start_time <= datetime.combine(grid_end, datetime.max.time()))
        .order_by(Schedule.start_time.asc())
        .all()
    )

    by_day = defaultdict(list)
    for s, a, e in rows:
        by_day[s.start_time.date()].append((s, a, e))

    days = []
    d = grid_start
    while d <= grid_end:
        days.append({
            "date": d,
            "in_month": (d.month == month and d.year == year),
            "is_today": (d == today),
            "is_weekend": d.weekday() >= 5,
            "attendances": by_day.get(d, []),
        })
        d += timedelta(days=1)

    # 本月合计(只算落在本月的考勤)
    totals = {"sessions": 0, "present": 0, "makeup": 0, "absent": 0, "leave": 0,
              "hours": 0.0, "value": 0.0}
    for s, a, e in rows:
        if s.start_time.date().month == month and s.start_time.date().year == year:
            totals["sessions"] += 1
            att = (a.attendance or "").lower()
            if att in totals:
                totals[att] += 1
            totals["hours"] += float(a.hours_used or 0)
            totals["value"] += float(a.hours_used or 0) * float(e.unit_price or 0)

    if month == 1:
        prev_y, prev_m = year - 1, 12
    else:
        prev_y, prev_m = year, month - 1
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1

    return {
        "days": days,
        "month_label": f"{year} 年 {month} 月",
        "year": year,
        "month": month,
        "prev_y": prev_y, "prev_m": prev_m,
        "next_y": next_y, "next_m": next_m,
        "totals": totals,
    }


@bp.route("/<int:sid>")
def detail(sid):
    student = Student.query.get_or_404(sid)
    enrollments = student.enrollments.order_by(Enrollment.enrolled_at.desc()).all()
    payments = student.payments.order_by(Payment.paid_at.desc()).all()
    refunds = student.refunds.order_by(Refund.refunded_at.desc()).all()

    # 财务/课时汇总(跨所有 enrollment)
    s_total = float(
        db.session.query(func.coalesce(func.sum(Enrollment.final_price), 0))
        .filter(Enrollment.student_id == sid, Enrollment.status != "refunded")
        .scalar() or 0
    )
    s_paid = float(
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.student_id == sid)
        .scalar() or 0
    )
    s_refunded = float(
        db.session.query(func.coalesce(func.sum(Refund.amount), 0))
        .filter(Refund.student_id == sid)
        .scalar() or 0
    )
    s_unsettled = max(0.0, s_total - s_paid)
    # 已购/已用/剩余跨所有非退费报名累加(与已用金额口径保持一致)
    s_hours_total = float(
        db.session.query(func.coalesce(func.sum(Enrollment.total_hours), 0))
        .filter(Enrollment.student_id == sid, Enrollment.status != "refunded")
        .scalar() or 0
    )
    s_hours_used = float(
        db.session.query(func.coalesce(func.sum(Enrollment.used_hours), 0))
        .filter(Enrollment.student_id == sid, Enrollment.status != "refunded")
        .scalar() or 0
    )

    # 学员角度的近期排期(通过 ScheduleAttendance 关联)
    from models import Schedule, ScheduleAttendance
    my_schedules = (
        db.session.query(Schedule)
        .join(ScheduleAttendance, ScheduleAttendance.schedule_id == Schedule.id)
        .join(Enrollment, ScheduleAttendance.enrollment_id == Enrollment.id)
        .filter(Enrollment.student_id == sid)
        .order_by(Schedule.start_time.desc())
        .limit(20)
        .all()
    )
    # 已用课时金额(按各 enrollment 自己的单价算)
    s_used_value = float(
        db.session.query(
            func.coalesce(func.sum(Enrollment.used_hours * Enrollment.unit_price), 0)
        )
        .filter(Enrollment.student_id == sid, Enrollment.status != "refunded")
        .scalar() or 0
    )
    # 课时平均单价:已用金额 / 已用课时
    s_avg_price = (s_used_value / s_hours_used) if s_hours_used > 0 else 0.0
    summary = {
        "total": s_total,        # 应付总额(不含已退费)
        "paid": s_paid,          # 已收款
        "refunded": s_refunded,  # 已退费
        "unsettled": s_unsettled,  # 未结
        "hours_total": s_hours_total,
        "hours_used": s_hours_used,
        "hours_remaining": max(0, s_hours_total - s_hours_used),
        "used_value": s_used_value,  # 已用课时金额
        "avg_price": s_avg_price,    # 课时平均单价
    }

    # 学员课程日历
    cal_year = request.args.get("cal_year", type=int)
    cal_month = request.args.get("cal_month", type=int)
    student_calendar = _build_student_calendar(sid, cal_year, cal_month)

    return render_template(
        "students/detail.html",
        student=student,
        enrollments=enrollments,
        payments=payments,
        refunds=refunds,
        summary=summary,
        my_schedules=my_schedules,
        student_calendar=student_calendar,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        s = Student(
            code=request.form.get("code") or _gen_student_code(),
            name=request.form.get("name", "").strip(),
            gender=request.form.get("gender", "unknown"),
            birth_date=_parse_date(request.form.get("birth_date")),
            id_card=request.form.get("id_card"),
            school=request.form.get("school"),
            grade=request.form.get("grade"),
            phone=request.form.get("phone"),
            address=request.form.get("address"),
            enrollment_date=_parse_date(request.form.get("enrollment_date")) or datetime.now().date(),
            status=request.form.get("status", "active"),
            notes=request.form.get("notes"),
        )
        if not s.name:
            flash("姓名必填", "error")
            return render_template("students/form.html", student=s, mode="new")
        db.session.add(s)
        db.session.commit()

        # 主联系人(可选)
        c_name = request.form.get("contact_name")
        c_phone = request.form.get("contact_phone")
        if c_name and c_phone:
            c = Contact(
                student_id=s.id,
                name=c_name,
                relationship=request.form.get("contact_relationship", "其他"),
                phone=c_phone,
                wechat=request.form.get("contact_wechat"),
                is_primary=True,
            )
            db.session.add(c)
            db.session.commit()

        flash("学员创建成功", "success")
        return redirect(url_for("students.detail", sid=s.id))
    return render_template("students/form.html", student=None, mode="new")


@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
def edit(sid):
    student = Student.query.get_or_404(sid)
    if request.method == "POST":
        student.code = request.form.get("code") or student.code
        student.name = request.form.get("name", "").strip() or student.name
        student.gender = request.form.get("gender", student.gender)
        student.birth_date = _parse_date(request.form.get("birth_date"))
        student.id_card = request.form.get("id_card")
        student.school = request.form.get("school")
        student.grade = request.form.get("grade")
        student.phone = request.form.get("phone")
        student.address = request.form.get("address")
        if request.form.get("enrollment_date"):
            student.enrollment_date = _parse_date(request.form.get("enrollment_date"))
        student.status = request.form.get("status", student.status)
        student.notes = request.form.get("notes")
        db.session.commit()
        flash("学员信息已更新", "success")
        return redirect(url_for("students.detail", sid=student.id))
    return render_template("students/form.html", student=student, mode="edit")


@bp.route("/<int:sid>/delete", methods=["POST"])
def delete(sid):
    student = Student.query.get_or_404(sid)
    if student.enrollments.count() > 0:
        flash("该学员有报名记录,不能删除,可改为'已退费'状态", "error")
        return redirect(url_for("students.detail", sid=sid))
    db.session.delete(student)
    db.session.commit()
    flash("学员已删除", "success")
    return redirect(url_for("students.list_view"))


# ---------- 联系人 ----------
@bp.route("/<int:sid>/contacts/add", methods=["POST"])
def add_contact(sid):
    student = Student.query.get_or_404(sid)
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    if not name or not phone:
        flash("联系人姓名和电话必填", "error")
        return redirect(url_for("students.detail", sid=sid) + "#contacts")
    is_primary = bool(request.form.get("is_primary"))
    if is_primary:
        for c in student.contacts:
            c.is_primary = False
    c = Contact(
        student_id=sid,
        name=name,
        relationship=request.form.get("relationship", "其他"),
        phone=phone,
        wechat=request.form.get("wechat"),
        is_primary=is_primary,
        notes=request.form.get("notes"),
    )
    db.session.add(c)
    db.session.commit()
    flash("联系人已添加", "success")
    return redirect(url_for("students.detail", sid=sid) + "#contacts")


@bp.route("/<int:sid>/contacts/<int:cid>/delete", methods=["POST"])
def delete_contact(sid, cid):
    c = Contact.query.get_or_404(cid)
    if c.student_id != sid:
        flash("联系人归属错误", "error")
        return redirect(url_for("students.detail", sid=sid))
    db.session.delete(c)
    db.session.commit()
    flash("联系人已删除", "success")
    return redirect(url_for("students.detail", sid=sid) + "#contacts")


@bp.route("/<int:sid>/contacts/<int:cid>/primary", methods=["POST"])
def set_primary(sid, cid):
    c = Contact.query.get_or_404(cid)
    if c.student_id != sid:
        flash("联系人归属错误", "error")
        return redirect(url_for("students.detail", sid=sid))
    for x in c.student.contacts:
        x.is_primary = (x.id == cid)
    db.session.commit()
    flash("已设为主联系人", "success")
    return redirect(url_for("students.detail", sid=sid) + "#contacts")


# ---------- helpers ----------
def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _gen_student_code():
    """生成学员编号 S + 年月日 + 4 位序号。"""
    today = datetime.now().strftime("%Y%m%d")
    last = (
        Student.query.filter(Student.code.like(f"S{today}%"))
        .order_by(Student.id.desc())
        .first()
    )
    if last and last.code:
        try:
            n = int(last.code[-4:]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"S{today}{n:04d}"
