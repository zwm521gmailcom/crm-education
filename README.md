# 教培 CRM

一个为教培行业(培训机构)设计的本地单机版学生关系管理系统。

> 适配范围:小型培训机构,1-2 个管理员,本机部署。功能聚焦:学员、课程、课时、费用、退费、排期考勤。

## ✨ 功能清单

| 模块 | 功能 |
|------|------|
| 🔐 登录 | 单管理员账号登录,会话 7 天 |
| 📊 仪表盘 | 在读学员数 / 剩余课时 / 本月营收 / 退费 / 近期排期 / 课时紧张学员 |
| 👨‍🎓 学员管理 | 学员登记、状态(在读/休学/结业/已退费)、联系人(可多个,可设主联系人) |
| 📖 课程管理 | 课程模板(学科/年级/班型/单价/默认课时包) |
| 📝 报名 | 学员报名某课程,购买课时包,记录实付/优惠/未结 |
| 🗓️ 排期 | 列表视图 + **日历视图**(按周显示,看每天的课次和出勤学员) |
| 👥 考勤 | 在排期里登记每个学员出勤/缺席/补课/请假,自动扣课时 |
| ⏱️ 课时流水 | 手工调整课时(赠送/扣减),每次操作记一笔账 |
| 💰 收款 | 登记每笔收款(类型/方式/时间),支持关联报名 |
| ↩️ 退费 | 登记退费,自动把报名置为已退费 |
| 📥 Excel 导出 | 学员/报名/收款/退费 一键导出 xlsx |
| 🔍 筛选 | 学员/课程/报名都支持搜索 + 状态过滤 |

## 🔐 默认账号

启动后用 `admin` / `admin123` 登录。建议首次登录后修改 `config.py` 里的 `SECRET_KEY`,并通过 `init_db.py --reset` 重建时改密码(或直接编辑数据库)。

## 🚀 启动方法

### 1. 安装 Python(本机还没装)

本机是 Windows,推荐用 winget 一键装:

```powershell
winget install -e --id Python.Python.3.12
```

装完关掉 PowerShell 重开,验证:

```powershell
python --version
pip --version
```

### 2. 装依赖

```powershell
cd C:\Users\Nancy\.minimax-agent-cn\projects\crm-education
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 第一次用 venv,如果提示"无法加载脚本,因为在此系统上禁止运行脚本",先执行:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. 初始化数据库(可选,带示例数据)

```powershell
python init_db.py
```

参数:
- `python init_db.py` —— 建表 + 写示例数据 + 创建默认管理员
- `python init_db.py --no-seed` —— 只建表和默认账号,不要示例
- `python init_db.py --reset` —— 删除旧库重建(!! 慎用,丢数据 !!)

### 4. 启动服务

```powershell
python run.py
```

浏览器打开:<http://127.0.0.1:5000> → 用 `admin` / `admin123` 登录

## 🚀 启动方法

### 1. 安装 Python(本机还没装)

本机是 Windows,推荐用 winget 一键装:

```powershell
winget install -e --id Python.Python.3.12
```

装完关掉 PowerShell 重开,验证:

```powershell
python --version
pip --version
```

### 2. 装依赖

```powershell
cd C:\Users\Nancy\.minimax-agent-cn\projects\crm-education
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 第一次用 venv,如果提示"无法加载脚本,因为在此系统上禁止运行脚本",先执行:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. 初始化数据库(可选,带示例数据)

```powershell
python init_db.py
```

参数:
- `python init_db.py` —— 建表 + 写示例数据(默认)
- `python init_db.py --no-seed` —— 只建表,不要示例
- `python init_db.py --reset` —— 删除旧库重建(!! 慎用,丢数据 !!)

### 4. 启动服务

```powershell
python run.py
```

浏览器打开:<http://127.0.0.1:5000>

## 📁 目录结构

```
crm-education/
├── app.py              # Flask 工厂 + 入口
├── run.py              # 启动脚本
├── config.py           # 配置
├── extensions.py       # SQLAlchemy 实例
├── models.py           # 数据模型(8 张表)
├── init_db.py          # 建表 + 示例数据
├── requirements.txt
├── README.md
├── instance/
│   └── crm.db          # SQLite 数据库(自动生成)
├── routes/             # 蓝图
│   ├── dashboard.py
│   ├── students.py
│   ├── courses.py
│   ├── enrollments.py
│   ├── schedules.py
│   ├── payments.py
│   └── refunds.py
├── templates/          # Jinja2 模板
│   ├── base.html
│   ├── dashboard.html
│   ├── students/ courses/ enrollments/ schedules/ payments/ refunds/
└── static/
    └── css/style.css
```

## 🗃️ 数据模型

- **Student** 学生(姓名/性别/出生/学校/年级/电话/状态)
- **Contact** 联系人(姓名/关系/电话/微信,一对多挂学生)
- **Course** 课程模板(学科/年级/班型/单价/默认课时包)
- **Enrollment** 报名(学员↔课程,购买课时,实付/优惠/未结)
- **Schedule** 排期(挂课程,老师/教室/时间/容量)
- **ScheduleAttendance** 出勤(排期↔报名,扣课时)
- **Payment** 收款(学员/报名/金额/方式/时间)
- **Refund** 退费(学员/报名/金额/原因/方式)

> 课时计算规则:
> - `Enrollment.used_hours` 在每次"出勤/补课"时累加,删除会回退
> - `remaining_hours = total_hours - used_hours`
> - 剩余为 0 时报名自动标记为"已用完"

## 💡 常见操作

| 场景 | 步骤 |
|------|------|
| 新学员报名并收款 | 学员管理 → 新增 → 然后"新报名" → 然后"收款" |
| 排一次课 | 课程详情 → 新排期 → 填时间/老师/教室 |
| 登记谁上了课 | 排期详情 → 添加出勤 → 选学员 + 出勤/补课(自动扣课时) |
| 学员转走要退费 | 学员详情 → 退费 → 选报名 → 填金额(会自动给建议) |
| 看本月营收 | 仪表盘 / 收款记录 |
| 哪些学员要续费了 | 仪表盘 → 课时紧张学员(剩余 ≤ 3) |

## 🔮 之后想加什么

- [x] 导出 Excel ✅
- [x] 学员课时流水 ✅
- [x] 多管理员 + 登录密码 ✅
- [x] 课表日历视图 ✅
- [ ] 学员请假补课自动排期
- [ ] 微信小程序家长端
- [ ] 排期冲突检测(同一老师同时段不能排两节课)

## ❓ 故障排查

- **打开页面 500 错误** —— 看 `instance/crm.db` 是否被其他程序占用,或检查 `pip install` 是否完整
- **数据库被锁** —— 杀掉所有 Python 进程,或重启电脑
- **中文乱码** —— 用 `python` (而非 `python3`),Python 3.7+ 默认 UTF-8
- **端口被占** —— 修改 `run.py` 里 `port=5000` 改成 `port=5001`
- **忘记密码** —— 用 SQLite 工具打开 `instance/crm.db`,在 users 表里手动改 password_hash 字段;或者重新 init_db(丢数据)

## 📜 License

MIT
