# Education CRM

> **🌐 Languages:** [中文](./README.md) | **English**

A local, single-machine Student Relationship Management system designed for the education/training industry.

> **Target users:** Small training institutions with 1-2 administrators, deployed on a local machine. Focused on: students, courses, lesson hours, fees, refunds, scheduling & attendance.

## ✨ Features

| Module | Description |
|--------|-------------|
| 🔐 Auth | Single admin account login, 7-day session |
| 📊 Dashboard | Active students / remaining hours / monthly revenue / refunds / upcoming schedule / students running low on hours |
| 👨‍🎓 Students | Student records, status (active / paused / graduated / refunded), multiple contacts (with primary designation) |
| 📖 Courses | Course templates (subject / grade / class type / unit price / default lesson package) |
| 📝 Enrollments | Student enrolls in a course, purchases lesson package, tracks paid / discount / outstanding |
| 🗓️ Schedule | List view + **calendar view** (weekly, showing daily sessions and attendees) |
| 👥 Attendance | Per-student attendance (present / absent / make-up / leave), auto-deducts lesson hours |
| ⏱️ Hour Adjustments | Manual hour adjustments (gift / deduct), each operation recorded in a log |
| 💰 Payments | Record each payment (type / method / time), linked to enrollment |
| ↩️ Refunds | Record refunds, auto-marks enrollment as refunded |
| 📥 Excel Export | One-click xlsx export for students / enrollments / payments / refunds |
| 🔍 Filtering | Search + status filter on students / courses / enrollments |

## 📸 Preview

### Desktop — Dashboard

![Dashboard Desktop](docs/screenshots/dashboard-desktop.png)

### Mobile — Responsive (< 600px auto-collapses to drawer sidebar)

![Dashboard Mobile](docs/screenshots/dashboard-mobile.png)

### Students Management

![Students List](docs/screenshots/students-list.png)

### Schedule Calendar (Weekly View)

![Schedule Calendar](docs/screenshots/schedule-calendar.png)

## 🔐 Default Credentials

Login with `admin` / `admin123`. **After first login, please**:
1. Change the `SECRET_KEY` in `config.py` (required before production)
2. Change the admin password in the admin backend

## 🚀 Quick Start

### Three ways to launch — pick one

#### Option A: One-click script (recommended for everyone)

**macOS / Linux**:
```bash
bash start.sh
```

**Windows**:
Double-click `start_crm.bat`

The script will: ① create/activate venv → ② install dependencies → ③ start `run.py` (**auto-init database + auto-open browser**)

#### Option B: Makefile (macOS / Linux devs)

```bash
make install      # install deps (auto-create venv)
make run          # start server (run.py will auto-init)
make init         # manual init (with sample data)
make init-empty   # init (without sample data)
make reset        # ⚠ wipe and rebuild database
make backup       # manual backup
make stop         # stop the server
```

#### Option C: Manual launch (all platforms)

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate              # macOS/Linux
# .\venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt

# 2. Launch (run.py auto-detects db; if missing, auto-inits)
python3 run.py
```

### Default Behavior

- **Port:** `5050` (override via `PORT=5050 python3 run.py`)
- **Database:** `instance/crm.db` (excluded by `.gitignore`, never committed)
- **Auto-init:** `run.py` detects missing db → **auto-calls** `init_db.py` with sample data
- **Auto-open browser:** `run.py` opens default browser on start (use `--no-browser` to disable)

### From GitHub

```bash
git clone https://github.com/your-username/crm-education.git
cd crm-education
bash start.sh              # or: make install && make run
# Browser opens → log in with admin / admin123
```

## 📁 Project Structure

```
crm-education/
├── app.py              # Flask factory + entry
├── run.py              # launcher (auto-init + auto-open browser)
├── start.sh            # macOS/Linux one-click launcher
├── start_crm.bat       # Windows one-click launcher
├── Makefile            # make run/init/reset/backup/stop
├── config.py           # configuration
├── extensions.py       # SQLAlchemy instance
├── models.py           # data models (9 tables, includes HourAdjustment log)
├── init_db.py          # schema + sample data + default admin
├── backup_now.py       # manual backup script
├── requirements.txt
├── README.md
├── README.en.md
├── CHANGELOG.md
├── .gitignore          # excludes db/venv/cache/logs
├── instance/           # runtime data (not in git)
│   ├── crm.db          # SQLite database (auto-generated)
│   ├── backups/        # automatic backups
│   └── *.log
├── routes/             # blueprints
│   ├── auth.py dashboard.py students.py courses.py
│   ├── enrollments.py schedules.py calendar.py
│   ├── payments.py refunds.py exports.py reports.py admin.py
├── templates/          # Jinja2 templates
│   ├── base.html
│   ├── dashboard.html
│   └── auth/ admin/ students/ courses/ enrollments/
│       schedules/ payments/ refunds/ reports/
└── static/
    └── css/style.css
```

## 🗃️ Data Model

- **Student** — student record (name / gender / birthdate / school / grade / phone / status)
- **Contact** — contact (name / relationship / phone / wechat, many-to-one with student)
- **Course** — course template (subject / grade / class type / unit price / default lesson package)
- **Enrollment** — enrollment (student↔course, purchased hours, paid / discount / outstanding)
- **Schedule** — class session (course / teacher / classroom / time / capacity)
- **ScheduleAttendance** — attendance (schedule↔enrollment, deducts hours)
- **Payment** — payment (student / enrollment / amount / method / time)
- **Refund** — refund (student / enrollment / amount / reason / method)
- **HourAdjustment** — manual hour adjustment log (gift / deduct)
- **User** — admin account (multi-admin support + bcrypt password)

> **Hour calculation rules:**
> - `Enrollment.used_hours` accumulates on each attendance / make-up; deletion rolls back
> - `remaining_hours = total_hours - used_hours`
> - When remaining hits 0, enrollment is auto-marked "exhausted"

## 💡 Common Operations

| Scenario | Steps |
|----------|-------|
| New student enrolls + pays | Students → New → "New Enrollment" → "Add Payment" |
| Schedule a class | Course detail → New Schedule → fill time / teacher / classroom |
| Log who attended | Schedule detail → Add Attendance → select students + status (auto-deducts hours) |
| Refund a leaving student | Student detail → Refund → select enrollment → fill amount (auto-suggests) |
| View this month's revenue | Dashboard / Payments page |
| Who needs to renew? | Dashboard → "Low Hours" students (remaining ≤ 3) |

## 🔮 Roadmap

- [x] Excel export ✅
- [x] Student hour adjustment log ✅
- [x] Multi-admin + login password ✅
- [x] Schedule calendar view ✅
- [x] Mobile responsive design ✅
- [ ] Auto-schedule student make-ups for leaves
- [ ] Schedule conflict detection (same teacher / same time slot)
- [ ] Dashboard charts (replacing current text-only stats)

## ❓ Troubleshooting

- **500 error on page load** — check if `instance/crm.db` is locked by another process; verify `pip install` completed
- **Database locked** — kill all Python processes or restart the computer
- **Garbled Chinese** — Python 3.7+ defaults to UTF-8; check the locale in `run.py` startup output
- **Port in use** — switch via `PORT=5051 python3 run.py`, or `make stop` first
- **Forgot password** — open `instance/crm.db` with a SQLite browser, edit the `password_hash` column in `users`; or `python3 init_db.py --reset` (wipes data)
- **macOS port 5000 occupied by ControlCe** — `run.py` defaults to 5050, already worked around

## 📜 License

MIT
