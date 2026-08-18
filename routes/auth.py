"""登录 / 退出。"""
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from functools import wraps

from extensions import db
from models import User

bp = Blueprint("auth", __name__)


def login_required(f):
    """保护需要登录的路由。"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    """从 session 取当前用户(没登录返回 None)。"""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("请输入用户名和密码", "error")
            return render_template("auth/login.html")
        user = User.query.filter_by(username=username, is_active=True).first()
        if not user or not user.check_password(password):
            flash("用户名或密码错误", "error")
            return render_template("auth/login.html")
        session.permanent = True
        session["user_id"] = user.id
        session["username"] = user.username
        user.last_login_at = datetime.now()
        db.session.commit()
        flash(f"欢迎回来,{user.display_name or user.username}", "success")
        next_url = request.args.get("next") or url_for("dashboard.index")
        return redirect(next_url)

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "success")
    return redirect(url_for("auth.login"))
