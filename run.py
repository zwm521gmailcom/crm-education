"""开发模式启动脚本。生产环境建议用 gunicorn / waitress。

特性:
- 启动前自动检测数据库:不存在则自动调用 init_db.py 初始化
- 可通过环境变量 PORT 覆盖端口(默认 5050,避免和 macOS ControlCe 占用的 5000 冲突)
- 启动后自动打开浏览器(除非传 --no-browser)
"""
import os
import sys
import threading
import time
import webbrowser


def ensure_database():
    """数据库不存在则自动调用 init_db.py 初始化。"""
    from app import create_app  # 延迟导入,避免日志太早刷出来

    app = create_app()
    db_path = os.path.join(os.path.dirname(__file__), "instance", "crm.db")
    if os.path.exists(db_path):
        return

    print("=" * 50)
    print("⚠️  检测到数据库不存在,自动初始化...")
    print("=" * 50)
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "init_db.py")],
        cwd=os.path.dirname(__file__),
    )
    if result.returncode != 0:
        sys.exit(f"❌ 初始化失败,请手动跑: python3 init_db.py")


def open_browser_later(url: str, delay: float = 1.5):
    """延迟打开浏览器,等服务起来后再开。"""
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    no_browser = "--no-browser" in sys.argv
    port = int(os.environ.get("PORT", 5050))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("DEBUG", "0") == "1"

    ensure_database()

    from app import create_app
    app = create_app()
    url = f"http://{host}:{port}"

    print(f"\n🚀 教培 CRM 启动中...")
    print(f"   浏览器: {url}")
    print(f"   默认账号: admin / admin123")
    print(f"   停止服务: Ctrl+C\n")

    if not no_browser:
        open_browser_later(url)

    app.run(host=host, port=port, debug=debug, use_reloader=debug)
