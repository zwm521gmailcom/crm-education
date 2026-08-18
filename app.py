"""Flask app 工厂 + 入口。"""
import os
from datetime import timedelta

from flask import Flask, redirect, request, session, url_for

from config import Config
from extensions import db


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)
    # session 有效期
    app.permanent_session_lifetime = timedelta(days=7)

    # 确保 instance 目录存在(SQLite 文件存放点)
    os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

    db.init_app(app)

    # 上传上限 100MB(数据库备份恢复用)
    app.config.setdefault("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)

    # 注册蓝图
    from routes.dashboard import bp as dashboard_bp
    from routes.students import bp as students_bp
    from routes.courses import bp as courses_bp
    from routes.enrollments import bp as enrollments_bp
    from routes.schedules import bp as schedules_bp
    from routes.calendar import bp as calendar_bp
    from routes.payments import bp as payments_bp
    from routes.refunds import bp as refunds_bp
    from routes.exports import bp as exports_bp
    from routes.reports import bp as reports_bp
    from routes.auth import bp as auth_bp
    from routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(courses_bp, url_prefix="/courses")
    app.register_blueprint(enrollments_bp, url_prefix="/enrollments")
    app.register_blueprint(schedules_bp, url_prefix="/schedules")
    app.register_blueprint(calendar_bp, url_prefix="/schedules")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(refunds_bp, url_prefix="/refunds")
    app.register_blueprint(exports_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # 全局登录保护:除 auth 蓝图和静态文件外,所有路由都要求登录
    @app.before_request
    def require_login():
        if request.endpoint is None:
            return None
        if request.endpoint.startswith("auth.") or request.endpoint == "static":
            return None
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return None

    # 把当前用户注入到所有模板
    from routes.auth import current_user

    @app.context_processor
    def inject_user():
        u = current_user()
        return {"current_user": u}

    # 根路径直接跳到仪表盘
    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    # Jinja 过滤器
    import models as _models  # noqa: F401

    @app.template_filter("money")
    def fmt_money(v):
        if v is None or v == "":
            return "0.00"
        try:
            return f"{float(v):,.2f}"
        except (TypeError, ValueError):
            return str(v)

    @app.template_filter("dt")
    def fmt_dt(v, fmt="%Y-%m-%d %H:%M"):
        if not v:
            return ""
        return v.strftime(fmt)

    @app.template_filter("date")
    def fmt_date(v, fmt="%Y-%m-%d"):
        if not v:
            return ""
        return v.strftime(fmt)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
