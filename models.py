"""数据模型。

表设计说明:
- User: 管理员账号
- Student: 学生本人信息
- Contact: 学生相关的紧急/主要联系人,一对多
- Course: 课程模板(产品)
- Enrollment: 学生报名某个课程的购买记录,一对多(同一学生可多次续报同一课程)
- Schedule: 课次排期,挂在 Course 下
- ScheduleAttendance: 排期里每个学生来上课的记录,扣课时
- Payment: 收款记录
- Refund: 退费记录
- HourAdjustment: 课时手工调整(赠送/补扣/调账)
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


# ---------- 通用 ----------
def now():
    return datetime.now()


# ---------- 用户(管理员) ----------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(64), default="管理员")
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def __repr__(self):
        return f"<User {self.username}>"


# ---------- 学生 ----------
class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True, comment="学员编号")
    name = db.Column(db.String(64), nullable=False, index=True)
    gender = db.Column(db.String(8), default="unknown")  # male/female/unknown
    birth_date = db.Column(db.Date, nullable=True)
    id_card = db.Column(db.String(32), nullable=True)
    school = db.Column(db.String(128), nullable=True, comment="在读学校")
    grade = db.Column(db.String(32), nullable=True, comment="年级")
    phone = db.Column(db.String(32), nullable=True, comment="本人电话")
    address = db.Column(db.String(255), nullable=True)
    enrollment_date = db.Column(db.Date, default=datetime.now().date)
    status = db.Column(db.String(16), default="active", index=True)
    # active 在读 / suspended 休学 / graduated 结业 / refunded 已退费
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    contacts = db.relationship(
        "Contact", backref="student", cascade="all, delete-orphan", lazy="dynamic"
    )
    enrollments = db.relationship(
        "Enrollment", backref="student", lazy="dynamic"
    )
    payments = db.relationship("Payment", backref="student", lazy="dynamic")
    refunds = db.relationship("Refund", backref="student", lazy="dynamic")

    @property
    def status_label(self):
        return {
            "active": "在读",
            "suspended": "休学",
            "graduated": "结业",
            "refunded": "已退费",
        }.get(self.status, self.status)

    @property
    def primary_contact(self):
        for c in self.contacts:
            if c.is_primary:
                return c
        return self.contacts.first()

    @property
    def total_remaining_hours(self):
        """所有进行中报名剩余课时之和。"""
        total = (
            db.session.query(func.coalesce(func.sum(Enrollment.total_hours - Enrollment.used_hours), 0))
            .filter(Enrollment.student_id == self.id, Enrollment.status == "active")
            .scalar()
        )
        return total or 0

    def __repr__(self):
        return f"<Student {self.code} {self.name}>"


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    relationship = db.Column(db.String(32), default="其他")  # 爸爸/妈妈/爷爷/奶奶/监护人/其他
    phone = db.Column(db.String(32), nullable=False)
    wechat = db.Column(db.String(64), nullable=True)
    is_primary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=now)


# ---------- 课程 ----------
class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    subject = db.Column(db.String(32), nullable=True, index=True)  # 学科
    grade_level = db.Column(db.String(32), nullable=True)
    class_type = db.Column(db.String(16), default="一对一")  # 一对一/小班/大班
    default_hours = db.Column(db.Integer, default=0, comment="默认课时包")
    unit_price = db.Column(db.Numeric(10, 2), default=0, comment="每课时单价")
    default_teacher = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), default="active", index=True)  # active/archived
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    enrollments = db.relationship("Enrollment", backref="course", lazy="dynamic")
    schedules = db.relationship("Schedule", backref="course", lazy="dynamic")

    @property
    def status_label(self):
        return "上架" if self.status == "active" else "下架"

    @property
    def default_total_price(self):
        try:
            return (self.default_hours or 0) * (self.unit_price or 0)
        except Exception:
            return Decimal(0)


# ---------- 报名(购买课时) ----------
class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True, comment="订单号")
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    total_hours = db.Column(db.Integer, nullable=False, default=0)
    used_hours = db.Column(db.Integer, nullable=False, default=0)
    unit_price = db.Column(db.Numeric(10, 2), default=0)
    total_price = db.Column(db.Numeric(10, 2), default=0)  # 应付总额
    discount = db.Column(db.Numeric(10, 2), default=0)  # 优惠
    final_price = db.Column(db.Numeric(10, 2), default=0)  # 实付
    price_source = db.Column(db.String(16), default="default")
    # default 课程默认价 / renewal 续费复刻(沿用上次) / manual 手动改 / promo 活动优惠
    status = db.Column(db.String(16), default="active", index=True)
    # active 进行中 / completed 已用完 / refunded 已退费 / paused 暂停
    enrolled_at = db.Column(db.Date, default=datetime.now().date)
    expires_at = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    attendances = db.relationship(
        "ScheduleAttendance", backref="enrollment", lazy="dynamic"
    )
    payments = db.relationship("Payment", backref="enrollment", lazy="dynamic")
    refunds = db.relationship("Refund", backref="enrollment", lazy="dynamic")

    @property
    def remaining_hours(self):
        return max(0, (self.total_hours or 0) - (self.used_hours or 0))

    @property
    def status_label(self):
        return {
            "active": "进行中",
            "completed": "已用完",
            "refunded": "已退费",
            "paused": "已暂停",
        }.get(self.status, self.status)

    @property
    def paid_amount(self):
        """已收款金额(不含退费)。"""
        return (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.enrollment_id == self.id)
            .scalar()
        ) or Decimal(0)

    @property
    def refunded_amount(self):
        return (
            db.session.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(Refund.enrollment_id == self.id)
            .scalar()
        ) or Decimal(0)

    @property
    def outstanding(self):
        """未结清金额 = 实付 - 已收 + 已退。"""
        try:
            return Decimal(self.final_price or 0) - Decimal(self.paid_amount) + Decimal(self.refunded_amount)
        except Exception:
            return Decimal(0)


# ---------- 排期 ----------
class Schedule(db.Model):
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    teacher = db.Column(db.String(64), nullable=True)
    classroom = db.Column(db.String(64), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    max_students = db.Column(db.Integer, default=1)
    hours_per_session = db.Column(db.Numeric(4, 1), default=1, comment="本课扣几课时")
    status = db.Column(db.String(16), default="scheduled", index=True)
    # scheduled/ongoing/completed/cancelled
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    attendances = db.relationship(
        "ScheduleAttendance", backref="schedule", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def status_label(self):
        return {
            "scheduled": "计划中",
            "ongoing": "进行中",
            "completed": "已完成",
            "cancelled": "已取消",
        }.get(self.status, self.status)

    @property
    def attended_count(self):
        return self.attendances.filter(
            ScheduleAttendance.attendance.in_(("present", "makeup"))
        ).count()


class ScheduleAttendance(db.Model):
    __tablename__ = "schedule_attendances"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False, index=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True)
    attendance = db.Column(db.String(16), default="present")
    # present 出勤 / absent 缺席 / makeup 补课 / leave 请假
    hours_used = db.Column(db.Numeric(4, 1), default=1)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def attendance_label(self):
        return {
            "present": "出勤",
            "absent": "缺席",
            "makeup": "补课",
            "leave": "请假",
        }.get(self.attendance, self.attendance)


# ---------- 费用 ----------
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True, comment="收据号")
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(16), default="enrollment")
    # enrollment 报名费 / renewal 续费 / material 教材 / other 其他
    payment_method = db.Column(db.String(16), default="wechat")
    # cash 现金 / wechat 微信 / alipay 支付宝 / bank 银行 / other 其他
    paid_at = db.Column(db.DateTime, default=now, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def type_label(self):
        return {
            "enrollment": "报名费",
            "renewal": "续费",
            "material": "教材",
            "other": "其他",
        }.get(self.payment_type, self.payment_type)

    @property
    def method_label(self):
        return {
            "cash": "现金",
            "wechat": "微信",
            "alipay": "支付宝",
            "bank": "银行",
            "other": "其他",
        }.get(self.payment_method, self.payment_method)


class Refund(db.Model):
    __tablename__ = "refunds"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    refund_method = db.Column(db.String(16), default="original")  # original 原路 / cash 现金 / other
    refunded_at = db.Column(db.DateTime, default=now, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def method_label(self):
        return {
            "original": "原路退回",
            "cash": "现金",
            "other": "其他",
        }.get(self.refund_method, self.refund_method)


# ---------- 课时手工调整 ----------
class HourAdjustment(db.Model):
    """手工调整:赠送/补扣/调账。每次调整要记一笔流水。"""
    __tablename__ = "hour_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True)
    change_hours = db.Column(db.Numeric(6, 1), nullable=False, comment="正数赠送/补回,负数扣减")
    reason = db.Column(db.String(255), nullable=True)
    operator = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=now)
