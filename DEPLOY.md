# 教培 CRM 部署文档

> 适用版本:本地单机版 Flask + SQLite,Windows 10/11 桌面部署
> 项目根目录:`C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education`
> 文档版本:v1.0 (2026-08-17)

---

## 一、部署架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    Windows 桌面 (本机)                          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │  浏览器       │◄──►│  Flask (5000)     │◄──►│  SQLite       │  │
│  │  admin/admin  │    │  venv\python      │    │  instance/    │  │
│  └──────────────┘    └──────────────────┘    │  crm.db       │  │
│                              │                └──────────────┘  │
│                              ▼                                 │
│                    ┌──────────────────┐                        │
│                    │  backups/ 目录     │ ◄─── 计划任务每日 23:00 │
│                    │  (自动 30 份)     │                        │
│                    └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

**核心特点:**
- 单进程 Flask 开发服务器(生产建议换 waitress)
- SQLite 本地文件,零外部依赖
- 12 个蓝图路由,7 天会话保持
- 桌面启动器(双 .bat 即可)

---

## 二、环境要求

### 2.1 操作系统
- ✅ Windows 10 1809+ / Windows 11
- ✅ Windows Server 2019+ (用于服务器部署)

### 2.2 运行时
| 组件 | 版本 | 备注 |
|------|------|------|
| Python | **3.12.x** | 3.11 也可,3.13 暂未测试 |
| pip | 23+ | 装 Python 自带 |
| 内存 | ≥ 1 GB 可用 | SQLite 内存占用极小 |
| 磁盘 | ≥ 500 MB | 主要是 venv + Python 本身 |

### 2.3 端口
- **5000** (Flask 默认) — 需在防火墙放行入站(本机访问可关)

### 2.4 浏览器
- Chrome / Edge / Firefox 任一现代浏览器

---

## 三、快速部署 (全新环境)

### 3.1 装 Python (本机没装的话)

```powershell
winget install -e --id Python.Python.3.12
```

装完关掉 PowerShell 重开,验证:

```powershell
python --version   # 应输出 Python 3.12.x
pip --version
```

### 3.2 解压项目 & 创建虚拟环境

```powershell
# 假设项目已经放在 C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education
cd C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education

# 如果 PowerShell 首次使用 venv,先放开执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 创建虚拟环境
python -m venv venv

# 激活
.\venv\Scripts\Activate.ps1

# 装依赖
pip install -r requirements.txt
```

**依赖列表 (来自 requirements.txt):**
```
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-WTF==1.2.1
WTForms==3.1.2
email-validator==2.2.0
openpyxl==3.1.5
```

### 3.3 初始化数据库

**首次部署(有示例数据,适合测试/演示):**
```powershell
python init_db.py
```

**正式环境(空库,只建表和默认账号):**
```powershell
python init_db.py --no-seed
```

**⚠️ 危险:重置数据库(丢所有数据):**
```powershell
python init_db.py --reset
```

初始化成功后会显示:
```
表已创建
已创建默认管理员: admin / admin123
```

> **必须改默认密码!** 见 §六 安全配置。

### 3.4 启动

**方式一:桌面启动器(推荐普通用户)**
```powershell
# 双击即可,或在 PowerShell 执行:
.\start_crm.bat
```
- 自动检测 5000 端口,已运行则直接打开浏览器
- 否则启动后台服务窗口(标题:教培 CRM - 服务窗口)
- 等待最多 15 秒,服务就绪后自动打开浏览器

**方式二:手动启动 (开发/调试)**
```powershell
.\venv\Scripts\Activate.ps1
python run.py
```
浏览器访问: <http://127.0.0.1:5000>

**方式三:生产模式(用 waitress,推荐)**
见 §四 生产部署。

---

## 四、生产部署 (推荐)

### 4.1 为什么不用 `python run.py`?

`run.py` 当前是 debug=True,会在代码改动时自动重启,**生产环境绝不要用**。

### 4.2 安装 waitress (Windows 友好 WSGI 服务器)

```powershell
.\venv\Scripts\Activate.ps1
pip install waitress
```

### 4.3 创建生产启动脚本

新建 `start_prod.bat`(项目根目录):

```batch
@echo off
chcp 65001 >nul
title 教培 CRM - 生产服务

cd /d "%~dp0"
call "%~dp0venv\Scripts\activate.bat"

set CRM_SECRET_KEY=替换成你的强随机密钥
set CRM_DB_URL=sqlite:///%~dp0instance\crm.db

:: 单 worker 即可(SQLite 不支持并发写)
waitress-serve --host=127.0.0.1 --port=5000 --threads=4 "app:create_app()"
```

### 4.4 生成强随机 SECRET_KEY

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
复制输出,粘贴到 `start_prod.bat` 的 `CRM_SECRET_KEY=` 后面。

### 4.5 配置 Windows 计划任务 (开机自启)

#### 方法一:用 schtasks 命令

```powershell
schtasks /Create /TN "CRMEdu Service" /TR "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\start_prod.bat" /SC ONSTART /RL HIGHEST /F
```

启动服务:
```powershell
schtasks /Run /TN "CRMEdu Service"
```

查看状态:
```powershell
schtasks /Query /TN "CRMEdu Service" /V /FO LIST
```

#### 方法二:用 PowerShell 计划任务

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\start_prod.bat" `
    -WorkingDirectory "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education"

$trigger = New-ScheduledTaskTrigger -AtStartup

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

Register-ScheduledTask -TaskName "CRMEdu Service" `
    -Action $action -Trigger $trigger -Principal $principal `
    -Description "教培 CRM 后台服务"
```

### 4.6 开机自启后的访问方式

服务在后台,用户:
- 双击桌面的 `start_crm.bat`(只起浏览器,不开服务)
- 或浏览器直接访问 <http://127.0.0.1:5000>

> **桌面快捷方式创建:** 在 `start_crm.bat` 上右键 → 发送到 → 桌面快捷方式。
> 还可以用项目自带的 `/admin/backup/shortcut/create` 路由一键创建(需先启动服务一次)。

---

## 五、备份与恢复

### 5.1 备份架构

```
instance/
├── crm.db              ← 当前数据库
├── backups/
│   ├── crm_backup_20260817_230000_auto.db   ← 每日自动
│   ├── crm_backup_20260817_143000_manual.db ← 手工
│   └── ... (最多保留 30 份自动备份)
├── flask.out.log       ← Flask stdout
├── flask.err.log       ← Flask stderr
└── backup_log.txt      ← 备份操作日志
```

### 5.2 配置每日自动备份 (Windows 计划任务)

#### 5.2.1 创建 `run_backup.bat`

```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0backup_now.py"
```

#### 5.2.2 创建计划任务 (每天 23:00)

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\run_backup.bat" `
    -WorkingDirectory "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education"

$trigger = New-ScheduledTaskTrigger -Daily -At "23:00"

Register-ScheduledTask -TaskName "CRMEdu Auto Backup" `
    -Action $action -Trigger $trigger `
    -Description "教培 CRM 每日自动备份 (保留 30 份)"
```

**验证备份是否正常:**
```powershell
# 手工跑一次
cd C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education
.\venv\Scripts\python.exe backup_now.py

# 看日志
Get-Content instance\backup_log.txt -Tail 20
```

### 5.3 手工备份

```powershell
# 方法一:用 backup_now.py(走与自动备份相同逻辑)
.\venv\Scripts\python.exe backup_now.py

# 方法二:浏览器界面:登录 → 后台管理 → 备份
```

### 5.4 恢复数据库

**⚠️ 恢复前先停服务,恢复后重启:**

```powershell
# 1. 停服务
schtasks /End /TN "CRMEdu Service"   # 如果是计划任务启动的
# 或手动关闭"教培 CRM - 服务窗口"

# 2. 备份当前库(以防万一)
Copy-Item instance\crm.db instance\crm.db.before-restore

# 3. 恢复
Copy-Item -Force instance\backups\crm_backup_YYYYMMDD_HHMMSS_auto.db instance\crm.db

# 4. 启动服务
schtasks /Run /TN "CRMEdu Service"
```

### 5.5 异地备份 (强烈推荐)

把 `instance/backups/` 定期同步到:
- 另一台机器(网盘/OneDrive)
- 外接硬盘
- NAS

简单方案 - 用 robocopy:
```powershell
robocopy "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\instance\backups" "D:\CRM-Backups" /MIR /Z /XA:H
```

或用 OneDrive/坚果云同步盘指向 `instance/backups` 目录。

---

## 六、安全配置

### 6.1 必须改的项

#### 6.1.1 改默认密码

```powershell
.\venv\Scripts\Activate.ps1
python -c "
from app import create_app
from extensions import db
from models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    u.set_password('你的新强密码(至少12位,大小写+数字+符号)')
    db.session.commit()
    print('密码已更新')
"
```

#### 6.1.2 设置 SECRET_KEY

`config.py` 第 8 行:
```python
SECRET_KEY = os.environ.get("CRM_SECRET_KEY", "dev-secret-change-me")
```

**生产环境必须设置环境变量,绝不能用默认值。**

设置方法:
```powershell
[System.Environment]::SetEnvironmentVariable('CRM_SECRET_KEY', '你的强随机密钥', 'User')
```
或写在 `.env` 文件(需 python-dotenv):
```powershell
pip install python-dotenv
```
新建 `.env`:
```
CRM_SECRET_KEY=你的强随机密钥
```

### 6.2 加固建议

- [ ] 改默认 `admin` 用户名
- [ ] 启用 Windows 防火墙,只允许本机访问 5000 端口
- [ ] 如果必须远程访问,用 `ssh -L 5000:127.0.0.1:5000 user@server` 端口转发
- [ ] 不要把项目目录放在 OneDrive/坚果云实时同步文件夹(可能锁住 SQLite 文件)
- [ ] 定期检查 `instance/flask.err.log` 看有没有异常请求

### 6.3 数据库位置自定义

如果想换盘符或路径,设置环境变量:
```powershell
$env:CRM_DB_URL = "sqlite:///" + "D:\CRMData\crm.db"
```
然后重启服务。**记得同步备份目录**。

---

## 七、配置参考

### 7.1 环境变量清单

| 变量 | 默认值 | 作用 |
|------|--------|------|
| `CRM_SECRET_KEY` | `dev-secret-change-me` | Flask session 加密密钥,**生产必须改** |
| `CRM_DB_URL` | `sqlite:///instance/crm.db` | 数据库位置,用于切盘/备份恢复 |

### 7.2 可调参数 (`config.py`)

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `WTF_CSRF_TIME_LIMIT` | `None` | 表单不设过期,生产建议改成 `3600` (1 小时) |
| `JSON_AS_ASCII` | `False` | JSON 响应保留中文(无需改) |
| `MAX_CONTENT_LENGTH` | 100 MB | 单次上传上限(备份恢复用) |

### 7.3 session 超时

`app.py` 第 15 行:
```python
app.permanent_session_lifetime = timedelta(days=7)
```
7 天免登录。改 1 天更安全:
```python
app.permanent_session_lifetime = timedelta(hours=8)
```

---

## 八、监控与日志

### 8.1 日志位置

| 日志 | 路径 | 大小控制 |
|------|------|----------|
| Flask stdout | `instance/flask.out.log` | 需手工归档 |
| Flask stderr | `instance/flask.err.log` | 需手工归档 |
| 备份日志 | `instance/backup_log.txt` | 自动累加 |
| wait 备份日志 | (无,需自己加) | - |

### 8.2 简易健康检查脚本

新建 `health_check.ps1`:
```powershell
$port = 5000
$url = "http://127.0.0.1:$port/dashboard"
try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) {
        Write-Host "[OK] 服务正常 (HTTP 200)" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "[WARN] 返回 HTTP $($r.StatusCode)" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "[FAIL] 服务不可达: $_" -ForegroundColor Red
    exit 2
}
```

挂到 Windows 计划任务,每 10 分钟跑一次,失败时触发邮件/IM 通知(用 PowerShell 脚本发 webhook)。

### 8.3 磁盘监控

`instance/crm.db` 持续增长。监控脚本:
```powershell
$db = "C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\instance\crm.db"
$sizeMB = [math]::Round((Get-Item $db).Length / 1MB, 2)
if ($sizeMB -gt 500) {
    Write-Host "[WARN] 数据库已 $sizeMB MB,建议归档" -ForegroundColor Yellow
}
```

---

## 九、升级与维护

### 9.1 应用升级

```powershell
# 1. 停服务
schtasks /End /TN "CRMEdu Service"

# 2. 备份当前库
Copy-Item instance\crm.db instance\backups\pre-upgrade-$(Get-Date -Format 'yyyyMMdd_HHmmss').db

# 3. 备份当前代码(以防回滚)
Copy-Item -Recurse C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education C:\Users\<USERNAME>\Desktop\crm-backup-$(Get-Date -Format 'yyyyMMdd') -Exclude venv,__pycache__

# 4. 拉新代码 / 解压新版本到项目目录(覆盖)
# (假设已用 git pull 或下载新压缩包)

# 5. 更新依赖(可能有新包)
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 6. 数据库迁移(如果有的话)
# python init_db.py  ← 只建新表,不会清空旧数据
# 或: alembic upgrade head  ← 如果后续引入 alembic

# 7. 启动
schtasks /Run /TN "CRMEdu Service"

# 8. 验证
Start-Sleep -Seconds 5
Get-Content instance\flask.err.log -Tail 50
```

### 9.2 库表结构升级

项目目前用 `db.create_all()`,**只能建新表,不能改字段**。
如需改字段(列类型/默认值),需要:
1. 用 SQLite 工具(DB Browser for SQLite)手动 ALTER
2. 或后续引入 Alembic 做迁移管理

### 9.3 日志清理

```powershell
# 每月清理一次 flask 日志
$logs = @("instance\flask.out.log", "instance\flask.err.log")
foreach ($log in $logs) {
    if ((Get-Item $log -ErrorAction SilentlyContinue).Length -gt 50MB) {
        # 归档最近 1000 行后清空
        Get-Content $log -Tail 1000 | Set-Content "${log}.archive"
        Clear-Content $log
    }
}
```

---

## 十、故障排查

### 10.1 服务起不来

| 症状 | 排查 |
|------|------|
| `Address already in use` | `netstat -ano \| findstr :5000` 看谁占用,杀掉或换端口 |
| `ModuleNotFoundError: No module named 'flask'` | 忘了激活 venv 或 `pip install` 没跑 |
| `sqlite3.OperationalError: database is locked` | 别的进程在用 db,关掉所有 Python 进程或重启电脑 |
| `ImportError: DLL load failed` | Python 3.12 + 旧版 venv 不兼容,删 `venv` 重装 |

### 10.2 页面 500 错误

1. 打开 `instance/flask.err.log` 拉到底,看 traceback
2. 90% 是改了代码导致 SQL 错误或 import 失败
3. 如果只是字符串格式问题,临时回滚代码;彻底修复后重启

### 10.3 备份失败

1. 看 `instance/backup_log.txt` 末行
2. 常见原因:
   - `instance/` 目录只读
   - 磁盘满
   - 路径权限不够
3. 验证:手工跑 `.\venv\Scripts\python.exe backup_now.py`

### 10.4 启动器打不开浏览器

- 浏览器路径有空格或非默认位置时,改 `start_crm.bat` 的 `start "" "%URL%"` 行为
- 防火墙拦截 PowerShell 联网
- 直接复制 <http://127.0.0.1:5000> 到浏览器

### 10.5 端口 5000 被占用

两种选择:
- **A. 换端口** — 改 `run.py` 和 `start_crm.bat`:
  ```python
  app.run(host="127.0.0.1", port=5001, debug=False)
  ```
- **B. 杀掉占用的进程**:
  ```powershell
  netstat -ano | findstr :5000
  taskkill /F /PID <pid>
  ```

### 10.6 启动后第一次访问很慢

SQLite 第一次执行 SQL 时会建索引缓存。后续访问快。
如持续慢,执行 `VACUUM` 整理:
```powershell
.\venv\Scripts\python.exe -c "
import sqlite3
conn = sqlite3.connect('instance/crm.db')
conn.execute('VACUUM')
conn.close()
print('VACUUM 完成')
"
```

### 10.7 忘记密码

```powershell
.\venv\Scripts\python.exe -c "
from app import create_app
from extensions import db
from models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    u.set_password('新密码')
    db.session.commit()
    print('密码已重置')
"
```

---

## 十一、性能与扩展性

### 11.1 当前性能基线 (2026-08 实际数据)

- 学员 ~60 人、排期 ~100、考勤 ~150
- 单表查询 < 50ms,仪表盘 < 300ms
- SQLite 库大小 ~200 KB
- 单进程 waitress 4 线程足够

### 11.2 何时该换 MySQL/PostgreSQL

- 学员 > 2000 人
- 并发用户 > 10
- 库 > 1 GB
- 需要跨机器访问

迁移路径:
1. 导出 SQLite 为 SQL
2. 在 MySQL/PG 创建空库,导入
3. 改 `CRM_DB_URL=mysql+pymysql://user:pass@host/db`
4. 装对应驱动 `pip install pymysql` 或 `psycopg2`
5. 重启

### 11.3 何时该加 Redis 缓存

- 目前不需要
- 如果仪表盘超过 2 秒,加 Flask-Caching

---

## 十二、目录速查

```
C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education\
├── app.py              # Flask 工厂
├── run.py              # 开发模式启动
├── config.py           # 配置类
├── extensions.py       # SQLAlchemy 实例
├── models.py           # 8 张表 + 业务方法
├── init_db.py          # 建表/示例/默认账号
├── backup_now.py        # 备份脚本(给计划任务)
├── start_crm.bat       # 桌面启动器
├── start_prod.bat      # (自建)生产启动
├── run_backup.bat      # (自建)备份启动
├── requirements.txt
├── README.md           # 用户手册
├── DEPLOY.md           # 本文档
├── instance/
│   ├── crm.db          # ★ 数据库(自动生成)
│   ├── backups/        # ★ 备份目录
│   ├── flask.out.log   # ★ Flask 输出
│   ├── flask.err.log   # ★ Flask 错误
│   └── backup_log.txt  # 备份日志
├── routes/             # 12 个蓝图
├── templates/          # Jinja2 模板
├── static/             # CSS/JS/图片
└── venv/               # 虚拟环境
```

---

## 十三、附录:常用 PowerShell 命令

```powershell
# 看服务在不在
Get-NetTCPConnection -LocalPort 5000 -State Listen

# 看 5000 端口谁占用
netstat -ano | findstr :5000

# 看 Flask 进程
Get-Process python -ErrorAction SilentlyContinue

# 杀 Flask 进程
Get-Process python | Stop-Process -Force

# 立刻重启服务
schtasks /End /TN "CRMEdu Service"; schtasks /Run /TN "CRMEdu Service"

# 备份数据库(SQLite 在线备份)
.\venv\Scripts\python.exe backup_now.py

# 看今天的 Flask 日志
Get-Content instance\flask.err.log -Tail 100

# 数据库完整性检查
.\venv\Scripts\python.exe -c "
import sqlite3
c = sqlite3.connect('instance/crm.db')
r = c.execute('PRAGMA integrity_check').fetchone()
print('integrity_check:', r[0] if r else 'unknown')
"

# 看数据库表行数
.\venv\Scripts\python.exe -c "
import sqlite3
c = sqlite3.connect('instance/crm.db')
for (name,) in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
    n = c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
    print(f'  {name}: {n} 行')
"
```

---

## 十四、附录:计划任务总览 (推荐配置)

| 任务名 | 触发器 | 动作 | 用户 |
|--------|--------|------|------|
| `CRMEdu Service` | 开机时 | 启动 `start_prod.bat` | SYSTEM |
| `CRMEdu Auto Backup` | 每天 23:00 | 启动 `run_backup.bat` | 当前用户 |
| `CRMEdu Log Cleanup` | 每月 1 日 03:00 | 跑日志归档脚本 | SYSTEM |

---

## 十五、联系与支持

- 项目作者:jackey
- 本地路径:`C:\Users\<USERNAME>\.minimax-agent-cn\projects\crm-education`
- README:同目录 `README.md` (用户功能说明)

> 任何部署问题,优先查 `instance/flask.err.log` 末 100 行,90% 能定位。
