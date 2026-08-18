"""初始化数据库 + 写入示例数据。

用法:
    python init_db.py            # 直接建表 + 写示例
    python init_db.py --no-seed  # 只建表,不要示例数据
    python init_db.py --reset    # 删掉旧库重建(!! 会丢数据 !!)
"""
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import (
    Contact,
    Course,
    Enrollment,
    Payment,
    Refund,
    Schedule,
    ScheduleAttendance,
    Student,
    User,
)


def main():
    seed = "--no-seed" not in sys.argv
    reset = "--reset" in sys.argv

    app = create_app()
    with app.app_context():
        db_path = os.path.join(os.path.dirname(__file__), "instance", "crm.db")
        if reset and os.path.exists(db_path):
            os.remove(db_path)
            print(f"已删除旧库: {db_path}")
        db.create_all()
        print("表已创建")

        # 默认管理员账号(如果还没有)
        if User.query.count() == 0:
            admin = User(username="admin", display_name="管理员")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("已创建默认管理员: admin / admin123")

        if not seed:
            print("已跳过示例数据 (--no-seed)")
            return

        if Student.query.count() > 0:
            print("数据库已有数据,跳过示例写入 (想重新来请用 --reset)")
            return

        # ---- 学员 ----
        s1 = Student(
            code="S202601150001",
            name="张小明",
            gender="male",
            birth_date=date(2012, 5, 12),
            school="实验小学",
            grade="六年级",
            phone="",
            address="阳光小区 12 号楼 301",
            enrollment_date=date(2025, 9, 1),
            status="active",
            notes="数学基础较好,粗心",
        )
        s2 = Student(
            code="S202601150002",
            name="李小红",
            gender="female",
            birth_date=date(2010, 8, 3),
            school="市一中",
            grade="初二",
            phone="13900001111",
            address="建设路 88 号",
            enrollment_date=date(2025, 7, 15),
            status="active",
        )
        s3 = Student(
            code="S202601150003",
            name="王浩",
            gender="male",
            birth_date=date(2015, 11, 22),
            school="附属幼儿园",
            grade="大班",
            enrollment_date=date(2026, 1, 10),
            status="active",
        )
        db.session.add_all([s1, s2, s3])
        db.session.flush()

        # 联系人
        c1 = Contact(student_id=s1.id, name="张父", relationship="父亲",
                     phone="13800001234", wechat="zhangfu_wx", is_primary=True)
        c2 = Contact(student_id=s1.id, name="张母", relationship="母亲",
                     phone="13800005678", is_primary=False)
        c3 = Contact(student_id=s2.id, name="李母", relationship="母亲",
                     phone="13900002222", is_primary=True)
        c4 = Contact(student_id=s3.id, name="王父", relationship="父亲",
                     phone="13700003333", is_primary=True)
        db.session.add_all([c1, c2, c3, c4])

        # ---- 课程 ----
        c_math = Course(
            code="C202601150001",
            name="小学数学思维训练",
            subject="数学",
            grade_level="小学",
            class_type="一对一",
            default_hours=40,
            unit_price=Decimal("180.00"),
            default_teacher="王老师",
            description="针对小学数学思维训练,提升解题能力",
            status="active",
        )
        c_eng = Course(
            code="C202601150002",
            name="初中英语同步课",
            subject="英语",
            grade_level="初中",
            class_type="小班",
            default_hours=60,
            unit_price=Decimal("120.00"),
            default_teacher="Sarah",
            description="人教版初二英语同步,6 人小班",
            status="active",
        )
        c_yuwen = Course(
            code="C202601150003",
            name="幼小衔接语文",
            subject="语文",
            grade_level="学前",
            class_type="一对一",
            default_hours=20,
            unit_price=Decimal("150.00"),
            default_teacher="刘老师",
            description="拼音 + 看图说话 + 识字",
            status="active",
        )
        db.session.add_all([c_math, c_eng, c_yuwen])
        db.session.flush()

        # ---- 报名 ----
        e1 = Enrollment(
            code="E202509010001",
            student_id=s1.id, course_id=c_math.id,
            total_hours=40, used_hours=8,
            unit_price=Decimal("180.00"),
            total_price=Decimal("7200.00"),
            discount=Decimal("200.00"),
            final_price=Decimal("7000.00"),
            status="active",
            enrolled_at=date(2025, 9, 1),
        )
        e2 = Enrollment(
            code="E202507150001",
            student_id=s2.id, course_id=c_eng.id,
            total_hours=60, used_hours=22,
            unit_price=Decimal("120.00"),
            total_price=Decimal("7200.00"),
            discount=Decimal("0"),
            final_price=Decimal("7200.00"),
            status="active",
            enrolled_at=date(2025, 7, 15),
        )
        e3 = Enrollment(
            code="E202601100001",
            student_id=s3.id, course_id=c_yuwen.id,
            total_hours=20, used_hours=1,
            unit_price=Decimal("150.00"),
            total_price=Decimal("3000.00"),
            discount=Decimal("0"),
            final_price=Decimal("3000.00"),
            status="active",
            enrolled_at=date(2026, 1, 10),
        )
        db.session.add_all([e1, e2, e3])
        db.session.flush()

        # ---- 收款记录 ----
        payments = [
            Payment(code="P202509010001", student_id=s1.id, enrollment_id=e1.id,
                    amount=Decimal("4000.00"), payment_type="enrollment",
                    payment_method="wechat", paid_at=datetime(2025, 9, 1, 10, 30),
                    notes="首次报名"),
            Payment(code="P202510150001", student_id=s1.id, enrollment_id=e1.id,
                    amount=Decimal("3000.00"), payment_type="renewal",
                    payment_method="wechat", paid_at=datetime(2025, 10, 15, 14, 0),
                    notes="续费"),
            Payment(code="P202507150001", student_id=s2.id, enrollment_id=e2.id,
                    amount=Decimal("7200.00"), payment_type="enrollment",
                    payment_method="alipay", paid_at=datetime(2025, 7, 15, 9, 0),
                    notes="一次性付清"),
            Payment(code="P202601100001", student_id=s3.id, enrollment_id=e3.id,
                    amount=Decimal("3000.00"), payment_type="enrollment",
                    payment_method="cash", paid_at=datetime(2026, 1, 10, 11, 0)),
        ]
        db.session.add_all(payments)

        # ---- 排期 + 出勤 ----
        now = datetime.now()
        schedules = [
            Schedule(course_id=c_math.id, teacher="王老师", classroom="A101",
                     start_time=now + timedelta(days=1, hours=2),
                     end_time=now + timedelta(days=1, hours=3, minutes=30),
                     max_students=1, hours_per_session=Decimal("1.5"),
                     status="scheduled"),
            Schedule(course_id=c_math.id, teacher="王老师", classroom="A101",
                     start_time=now - timedelta(days=7),
                     end_time=now - timedelta(days=7, minutes=-90),
                     max_students=1, hours_per_session=Decimal("1.5"),
                     status="completed"),
            Schedule(course_id=c_eng.id, teacher="Sarah", classroom="B202",
                     start_time=now + timedelta(days=2, hours=3),
                     end_time=now + timedelta(days=2, hours=4, minutes=30),
                     max_students=6, hours_per_session=Decimal("1.5"),
                     status="scheduled"),
            Schedule(course_id=c_yuwen.id, teacher="刘老师", classroom="A103",
                     start_time=now - timedelta(days=3),
                     end_time=now - timedelta(days=3, minutes=-60),
                     max_students=1, hours_per_session=Decimal("1"),
                     status="completed"),
        ]
        # 上面 end_time 占位不对,这里重新算:开始时间 + 课程时长
        schedules[1].end_time = schedules[1].start_time + timedelta(hours=1, minutes=30)
        schedules[3].end_time = schedules[3].start_time + timedelta(hours=1)
        db.session.add_all(schedules)
        db.session.flush()

        # 出勤(过去的排期)
        att1 = ScheduleAttendance(
            schedule_id=schedules[1].id, enrollment_id=e1.id,
            attendance="present", hours_used=Decimal("1.5"))
        att2 = ScheduleAttendance(
            schedule_id=schedules[3].id, enrollment_id=e3.id,
            attendance="present", hours_used=Decimal("1"))
        db.session.add_all([att1, att2])

        db.session.commit()
        print("示例数据写入完成")
        print(f"  学员: {Student.query.count()}")
        print(f"  联系人: {Contact.query.count()}")
        print(f"  课程: {Course.query.count()}")
        print(f"  报名: {Enrollment.query.count()}")
        print(f"  收款: {Payment.query.count()}")
        print(f"  排期: {Schedule.query.count()}")
        print(f"  出勤: {ScheduleAttendance.query.count()}")


if __name__ == "__main__":
    main()
