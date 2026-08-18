"""数据库备份 / 恢复 / 定时 / 桌面快捷方式。

设计要点:
- 用 SQLite 在线 backup API(可热备,不锁库)
- 文件名强校验,防路径穿越
- 恢复前自动留一份 pre_restore 快照,可一键回退
- 上传文件做 SQLite 完整性校验(quick_check + 必须含 students 表)
- 限定 .db / .sqlite / .sqlite3 三种扩展名
- 恢复会 dispose SQLAlchemy 连接池,下一次请求会重建
- 定时备份:走 Windows 计划任务(schtasks),无需 Flask 进程常驻
- 桌面快捷方式:指向 start_crm.bat,双击即启+开浏览器
"""
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from extensions import db


bp = Blueprint("admin", __name__)


# 备份目录(放在 instance/backups/)
BACKUP_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
    "instance",
    "backups",
)

# 文件名合法性:只允许自动生成的时间戳格式
#   crm_backup_20260811_213045.db
#   crm_backup_20260811_213045_describe.db
#   crm_pre_restore_20260811_213045.db
SAFE_NAME_RE = re.compile(
    r"^crm_(?:backup|pre_restore)_\d{8}_\d{6}(?:_[A-Za-z0-9_\-]{1,40})?\.db$"
)

# 手动备份保留最新多少个(pre_restore 永不过期)
MAX_BACKUPS = 30

# 单次上传上限 100MB(在 create_app 里也设了 MAX_CONTENT_LENGTH)


def _current_db_path():
    """从 SQLALCHEMY_DATABASE_URI 解出 .db 文件的绝对路径。"""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        return uri[len("sqlite:///"):]
    if uri.startswith("sqlite://"):
        # 相对路径
        return os.path.join(current_app.root_path, uri[len("sqlite://"):])
    raise RuntimeError("仅支持 SQLite 数据库")


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _do_safe_backup(src_path, dst_path):
    """SQLite 在线 backup API,可在库被读写的同时安全备份。"""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def _is_valid_sqlite_file(path):
    """校验文件是有效的 SQLite 数据库,且是本系统能识别的(student 表存在)。"""
    if not os.path.isfile(path):
        return False, "文件不存在"
    sz = os.path.getsize(path)
    if sz < 100:
        return False, "文件过小,不是有效数据库"
    try:
        conn = sqlite3.connect(path)
        try:
            cur = conn.execute("PRAGMA quick_check")
            row = cur.fetchone()
            if not row or row[0] != "ok":
                return False, f"数据库校验失败: {row[0] if row else '?'}"
            cur = conn.execute("PRAGMA user_version")
            ver = cur.fetchone()[0] or 0
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='students'"
            )
            if not cur.fetchone():
                return False, "缺少 students 表,可能不是本系统的数据库"
            return True, f"有效 (user_version={ver}, 大小 {_fmt_size(sz)})"
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        return False, f"SQLite 错误: {e}"


def _fmt_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def _list_backups():
    """列所有备份,按时间倒序。"""
    _ensure_backup_dir()
    files = []
    for fname in os.listdir(BACKUP_DIR):
        if not fname.endswith(".db"):
            continue
        if not SAFE_NAME_RE.match(fname):
            continue
        fpath = os.path.join(BACKUP_DIR, fname)
        try:
            st = os.stat(fpath)
        except OSError:
            continue
        files.append({
            "name": fname,
            "path": fpath,
            "size": st.st_size,
            "size_text": _fmt_size(st.st_size),
            "mtime": datetime.fromtimestamp(st.st_mtime),
            "kind": "pre_restore" if fname.startswith("crm_pre_restore_") else "manual",
        })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


def _rotate_backups():
    """手动备份保留最新 MAX_BACKUPS 个,删旧的。"""
    files = _list_backups()
    manuals = [f for f in files if f["kind"] == "manual"]
    for f in manuals[MAX_BACKUPS:]:
        try:
            os.remove(f["path"])
        except OSError:
            pass


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ============== 项目根目录 ==============
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
BACKUP_SCRIPT = os.path.join(PROJECT_DIR, "backup_now.py")
START_BAT = os.path.join(PROJECT_DIR, "start_crm.bat")
BACKUP_LOG = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
    "instance",
    "backup_log.txt",
)
TASK_NAME = "CRM_Backup"  # Windows 计划任务名(英文避免编码坑)
DESKTOP_SHORTCUT_NAME = "教培CRM.lnk"


# ============== 计划任务(定时备份) ==============

def _schtasks(args, timeout=15):
    """Run schtasks, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["schtasks"] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
    except FileNotFoundError:
        return -1, "", "schtasks 不在 PATH(本机非 Windows?)"
    except subprocess.TimeoutExpired:
        return -2, "", "schtasks 执行超时"
    except Exception as e:
        return -3, "", f"执行失败: {e}"


def get_schedule_info():
    """查询当前定时任务状态。返回 dict 或 None。"""
    code, out, err = _schtasks(["/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
    if code != 0:
        return None
    info = {"name": TASK_NAME, "raw": out, "err": err}
    for line in out.splitlines():
        line = line.strip()
        for key in ("Status", "Last Run Time", "Last Run Result",
                    "Next Run Time", "Schedule Type", "Start Time",
                    "Days", "Run As User"):
            prefix = key + ":"
            if line.startswith(prefix):
                val = line[len(prefix):].strip()
                info[key.lower().replace(" ", "_")] = val
    return info


def _validate_time(s):
    """校验 HH:MM 格式。"""
    if not s:
        return None
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def create_schedule(sched_type, time_str=None, weekday=None, interval=None):
    """创建定时备份任务(总是先删后建)。

    sched_type: 'daily' | 'weekly' | 'hourly'
    time_str: HH:MM 格式
    weekday: 'MON'|'TUE'|...|'SUN'
    interval: 1-23
    """
    project_dir = PROJECT_DIR
    python_exe = os.path.join(project_dir, "venv", "Scripts", "python.exe")
    if not os.path.isfile(python_exe):
        return False, f"找不到 Python: {python_exe}"
    if not os.path.isfile(BACKUP_SCRIPT):
        return False, f"找不到备份脚本: {BACKUP_SCRIPT}"
    tr = f'"{python_exe}" "{BACKUP_SCRIPT}"'

    # 先删再建(schtasks 不支持 update,只能 delete + create)
    _schtasks(["/Delete", "/TN", TASK_NAME, "/F"])

    args = ["/Create", "/TN", TASK_NAME, "/TR", tr, "/F"]
    if sched_type == "daily":
        t = _validate_time(time_str)
        if not t:
            return False, "每日计划需要 HH:MM 格式时间"
        args += ["/SC", "DAILY", "/ST", t]
    elif sched_type == "weekly":
        t = _validate_time(time_str)
        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        if not t or not weekday or weekday not in valid_days:
            return False, "每周计划需要 HH:MM 时间和有效的星期(MON-SUN)"
        args += ["/SC", "WEEKLY", "/D", weekday, "/ST", t]
    elif sched_type == "hourly":
        try:
            n = int(interval)
        except (TypeError, ValueError):
            return False, "每小时计划需要 1-23 之间的数字"
        if not (1 <= n <= 23):
            return False, "间隔必须在 1-23 小时之间"
        args += ["/SC", "HOURLY", "/MO", str(n)]
    else:
        return False, f"未知计划类型: {sched_type}"

    code, out, err = _schtasks(args)
    if code != 0:
        # schtasks 经常因权限失败(非管理员)
        msg = err or out or f"schtasks 退出码 {code}"
        if "Access is denied" in msg or code == 1:
            msg += " · 提示:创建计划任务需要管理员权限,可用管理员打开 PowerShell 手动跑命令"
        return False, msg
    return True, f"已创建 {sched_type} 计划任务"


def delete_schedule():
    code, out, err = _schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
    if code == 0:
        return True, "已删除"
    # 任务不存在也算成功
    if "does not exist" in (err + out).lower() or "找不到" in (err + out):
        return True, "任务本就不存在"
    return False, err or out or f"schtasks 退出码 {code}"


def _get_desktop_path():
    """拿桌面路径,优先 %USERPROFILE%\\Desktop,fallback 到 Known Folders API。"""
    candidates = []
    home = Path.home()
    candidates.append(home / "Desktop")
    candidates.append(home / "桌面")
    # 公共桌面
    public = Path(os.environ.get("PUBLIC", "C:/Users/Public"))
    candidates.append(public / "Desktop")
    candidates.append(public / "桌面")
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def create_desktop_shortcut():
    """在桌面创建一键启动的快捷方式(.lnk),指向 start_crm.bat。

    用 PowerShell + WScript.Shell COM 创建。
    """
    desktop = _get_desktop_path()
    if desktop is None:
        return False, "找不到桌面目录"

    lnk_path = desktop / DESKTOP_SHORTCUT_NAME
    bat_path = START_BAT

    if not os.path.isfile(bat_path):
        return False, f"启动脚本不存在: {bat_path}"

    # 用 PowerShell 创建 .lnk(必须用 [Environment]::CurrentDirectory 之类避免引号问题)
    ps_script = f"""$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop '{DESKTOP_SHORTCUT_NAME}'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = '{bat_path.replace(chr(92), chr(92)+chr(92))}'
$sc.WorkingDirectory = '{PROJECT_DIR.replace(chr(92), chr(92)+chr(92))}'
$sc.IconLocation = 'C:\\Windows\\System32\\shell32.dll,13'
$sc.Description = '教培 CRM - 一键启动并打开浏览器'
$sc.WindowStyle = 7
$sc.Save()
Write-Output "OK:$lnk"
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15,
        )
    except FileNotFoundError:
        return False, "PowerShell 不在 PATH"
    except subprocess.TimeoutExpired:
        return False, "PowerShell 执行超时"
    except Exception as e:
        return False, f"执行失败: {e}"

    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "未知错误").strip()

    if not lnk_path.exists():
        return False, f"创建失败,文件未生成: {lnk_path}"

    return True, str(lnk_path)


def read_backup_log(n=20):
    """读最近的 n 条备份日志(从 instance/backup_log.txt)。"""
    if not os.path.isfile(BACKUP_LOG):
        return []
    try:
        with open(BACKUP_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [ln.rstrip("\n") for ln in lines[-n:][::-1]]
    except OSError:
        return []


# ============== 路由 ==============


@bp.route("/backup")
def backup():
    """备份列表 + 当前库信息 + 定时状态 + 快捷方式状态。"""
    db_path = _current_db_path()
    db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path)) if os.path.isfile(db_path) else None
    backups = _list_backups()
    # 定时任务
    schedule = get_schedule_info()
    schedule_log = read_backup_log(15)
    # 桌面快捷方式
    desktop = _get_desktop_path()
    shortcut_path = (desktop / DESKTOP_SHORTCUT_NAME) if desktop else None
    shortcut_exists = bool(shortcut_path and shortcut_path.exists())
    return render_template(
        "admin/backup.html",
        db_path=db_path,
        db_size=db_size,
        db_size_text=_fmt_size(db_size),
        db_mtime=db_mtime,
        backups=backups,
        max_backups=MAX_BACKUPS,
        schedule=schedule,
        schedule_log=schedule_log,
        shortcut_exists=shortcut_exists,
        shortcut_path=str(shortcut_path) if shortcut_path else None,
        desktop_path=str(desktop) if desktop else None,
    )


@bp.route("/backup/run-now", methods=["POST"])
def backup_run_now():
    """立即执行一次备份(同步调用 backup_now.py)。"""
    if not os.path.isfile(BACKUP_SCRIPT):
        flash("找不到 backup_now.py 脚本", "error")
        return redirect(url_for("admin.backup"))
    python_exe = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")
    try:
        result = subprocess.run(
            [python_exe, BACKUP_SCRIPT],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
        )
        if result.returncode == 0:
            # 解析最后一行 SUCCESS 找到文件名
            last = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
            flash(f"✅ 备份已执行: {last or '完成'}", "success")
        else:
            err = (result.stderr or result.stdout or "未知错误").strip()
            flash(f"❌ 备份失败: {err[-200:]}", "error")
    except subprocess.TimeoutExpired:
        flash("❌ 备份超时(>120s)", "error")
    except Exception as e:
        flash(f"❌ 执行失败: {e}", "error")
    return redirect(url_for("admin.backup"))


@bp.route("/backup/schedule", methods=["POST"])
def backup_schedule_save():
    """创建 / 更新定时备份任务。"""
    sched_type = (request.form.get("type") or "").strip()
    time_str = (request.form.get("time") or "").strip()
    weekday = (request.form.get("weekday") or "SUN").strip()
    interval = (request.form.get("interval") or "6").strip()
    if sched_type not in ("daily", "weekly", "hourly"):
        flash("无效的计划类型", "error")
        return redirect(url_for("admin.backup"))
    ok, msg = create_schedule(sched_type, time_str, weekday, interval)
    flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "error")
    return redirect(url_for("admin.backup"))


@bp.route("/backup/schedule/delete", methods=["POST"])
def backup_schedule_delete():
    """删除定时备份任务。"""
    ok, msg = delete_schedule()
    flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "error")
    return redirect(url_for("admin.backup"))


@bp.route("/backup/shortcut/create", methods=["POST"])
def backup_create_shortcut():
    """在桌面创建一键启动的快捷方式。"""
    ok, msg = create_desktop_shortcut()
    flash(("✅ 已创建:" if ok else "❌ 创建失败:") + msg, "success" if ok else "error")
    return redirect(url_for("admin.backup"))


@bp.route("/backup", methods=["POST"])
def backup_create():
    """创建一个新的手动备份。"""
    _ensure_backup_dir()
    db_path = _current_db_path()
    if not os.path.isfile(db_path):
        flash(f"当前数据库不存在: {db_path}", "error")
        return redirect(url_for("admin.backup"))

    label = re.sub(r"[^A-Za-z0-9_\-]", "", (request.form.get("label") or "").strip())[:40]
    suffix = f"_{label}" if label else ""
    fname = f"crm_backup_{_ts()}{suffix}.db"
    dst = os.path.join(BACKUP_DIR, fname)
    try:
        _do_safe_backup(db_path, dst)
        flash(f"备份已创建: {fname}", "success")
    except Exception as e:
        flash(f"备份失败: {e}", "error")
    _rotate_backups()
    return redirect(url_for("admin.backup"))


@bp.route("/backup/download/<name>")
def backup_download(name):
    """下载一个备份文件。"""
    if not SAFE_NAME_RE.match(name):
        abort(400, "非法文件名")
    fpath = os.path.join(BACKUP_DIR, name)
    if not os.path.isfile(fpath):
        abort(404, "备份不存在")
    return send_file(
        fpath,
        as_attachment=True,
        download_name=name,
        mimetype="application/octet-stream",
    )


@bp.route("/backup/delete/<name>", methods=["POST"])
def backup_delete(name):
    """删除一个备份(pre_restore 也能删)。"""
    if not SAFE_NAME_RE.match(name):
        flash("非法文件名", "error")
        return redirect(url_for("admin.backup"))
    fpath = os.path.join(BACKUP_DIR, name)
    if os.path.isfile(fpath):
        _safe_remove(fpath)
        flash(f"已删除: {name}", "success")
    else:
        flash("备份不存在", "error")
    return redirect(url_for("admin.backup"))


@bp.route("/restore")
def restore():
    """恢复页:支持两种来源(上传 / 已有备份),强制二次确认。"""
    db_path = _current_db_path()
    db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path)) if os.path.isfile(db_path) else None
    backups = _list_backups()
    return render_template(
        "admin/restore.html",
        db_path=db_path,
        db_size=db_size,
        db_size_text=_fmt_size(db_size),
        db_mtime=db_mtime,
        backups=backups,
    )


@bp.route("/restore", methods=["POST"])
def restore_apply():
    """执行恢复。两种来源:file 上传 / backup 选已有快照。"""
    db_path = _current_db_path()
    if not os.path.isfile(db_path):
        flash("当前数据库文件不存在,无法恢复", "error")
        return redirect(url_for("admin.restore"))

    # 二次确认
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "RESTORE":
        flash('请在确认框中输入大写 "RESTORE" 字样后再提交', "error")
        return redirect(url_for("admin.restore"))

    source = (request.form.get("source") or "").strip()
    upload = request.files.get("file")
    selected = (request.form.get("selected_backup") or "").strip()
    tmp_path = None

    # 决定要恢复的源文件
    if source == "upload":
        if not upload or not upload.filename:
            flash("请选择要上传的备份文件", "error")
            return redirect(url_for("admin.restore"))
        lower = upload.filename.lower()
        if not (lower.endswith(".db") or lower.endswith(".sqlite") or lower.endswith(".sqlite3")):
            flash("只支持 .db / .sqlite / .sqlite3 文件", "error")
            return redirect(url_for("admin.restore"))
        safe = secure_filename(upload.filename) or "uploaded.db"
        tmp_path = os.path.join(BACKUP_DIR, f"_tmp_upload_{_ts()}_{int(time.time())}_{safe}")
        try:
            upload.save(tmp_path)
        except Exception as e:
            flash(f"上传失败: {e}", "error")
            return redirect(url_for("admin.restore"))
        candidate = tmp_path
    elif source == "backup":
        if not selected or not SAFE_NAME_RE.match(selected):
            flash("请选择要恢复的备份", "error")
            return redirect(url_for("admin.restore"))
        candidate = os.path.join(BACKUP_DIR, selected)
        if not os.path.isfile(candidate):
            flash("备份文件不存在", "error")
            return redirect(url_for("admin.restore"))
    else:
        flash("请选择恢复来源(上传文件 / 已有备份)", "error")
        return redirect(url_for("admin.restore"))

    # 校验候选文件
    valid, msg = _is_valid_sqlite_file(candidate)
    if not valid:
        if tmp_path:
            _safe_remove(tmp_path)
        flash(f"文件无效: {msg}", "error")
        return redirect(url_for("admin.restore"))

    # 恢复前先备份当前
    pre_fname = f"crm_pre_restore_{_ts()}.db"
    pre_path = os.path.join(BACKUP_DIR, pre_fname)
    _ensure_backup_dir()
    try:
        _do_safe_backup(db_path, pre_path)
    except Exception as e:
        if tmp_path:
            _safe_remove(tmp_path)
        flash(f"恢复中止:当前库备份失败 {e}", "error")
        return redirect(url_for("admin.restore"))

    # 关掉 SQLAlchemy 所有连接,让 backup() 能独占
    try:
        db.session.remove()
        db.engine.dispose()
    except Exception as e:
        flash(f"恢复中止:关闭连接失败 {e}", "error")
        return redirect(url_for("admin.restore"))

    # 用 SQLite backup API 把候选数据复制到当前库(覆盖)
    try:
        current = sqlite3.connect(db_path)
        source_db = sqlite3.connect(candidate)
        try:
            with current:
                source_db.backup(current)
        finally:
            current.close()
            source_db.close()
    except Exception as e:
        flash(f"恢复失败: {e}。当前数据未变更(快照在 {pre_fname})", "error")
        if tmp_path:
            _safe_remove(tmp_path)
        return redirect(url_for("admin.restore"))

    # 清理临时上传
    if tmp_path:
        _safe_remove(tmp_path)

    flash(
        f"恢复成功 ✅ 当前数据库已替换为新内容。恢复前快照:{pre_fname}。",
        "success",
    )
    return redirect(url_for("admin.backup"))
