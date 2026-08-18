"""Flask 配置。"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("CRM_SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "CRM_DB_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "crm.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False  # 让 JSON 响应正确显示中文
    WTF_CSRF_TIME_LIMIT = None  # 表单不设过期
