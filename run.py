"""开发模式启动脚本。生产环境建议用 gunicorn / waitress。"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
