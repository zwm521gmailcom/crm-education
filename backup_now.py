"""命令行备份脚本(给 Windows 计划任务调用)。

独立运行,无 Flask 依赖,失败也写日志不抛异常。
"""
import glob
import os
import sqlite3
import sys
import traceback
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(SCRIPT_DIR, "instance")
SRC = os.path.join(INSTANCE_DIR, "crm.db")
BACKUP_DIR = os.path.join(INSTANCE_DIR, "backups")
LOG = os.path.join(INSTANCE_DIR, "backup_log.txt")

MAX_AUTO = 30  # 自动备份保留份数(_auto 后缀的)


def log(msg):
    line = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def make_backup():
    if not os.path.isfile(SRC):
        log(f"FAILED: 源数据库不存在 {SRC}")
        return False
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"crm_backup_{ts}_auto.db")
    try:
        src = sqlite3.connect(SRC)
        dstc = sqlite3.connect(dst)
        try:
            with dstc:
                src.backup(dstc)
        finally:
            dstc.close()
            src.close()
        size = os.path.getsize(dst)
        log(f"SUCCESS: {os.path.basename(dst)} ({size} bytes)")
        return True
    except Exception as e:
        log(f"FAILED: {e}")
        log(traceback.format_exc())
        return False


def cleanup_old_auto():
    """清理老的 _auto 备份,保留最新 MAX_AUTO 份。"""
    try:
        files = sorted(glob.glob(os.path.join(BACKUP_DIR, "crm_backup_*_auto.db")))
        for old in files[:-MAX_AUTO] if len(files) > MAX_AUTO else []:
            try:
                os.remove(old)
                log(f"CLEANUP: removed {os.path.basename(old)}")
            except OSError as e:
                log(f"CLEANUP_FAILED: {e}")
    except Exception as e:
        log(f"CLEANUP_ERROR: {e}")


def main():
    ok = make_backup()
    cleanup_old_auto()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
