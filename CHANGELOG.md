# 更新日志

本项目的所有重要改动都记录在此文件。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [未发布] - 进行中

### 计划中
- 学员请假补课自动排期
- 排期冲突检测(同一老师同时段不能排两节课)

## [v1.1.0] - 2026-08-18

### 新增
- 🍔 **全站移动端自适应** — 三档断点(桌面 4 列 / 平板 2 列 / 手机 1 列 + 抽屉式侧边栏)
  - 侧边栏在 < 600px 自动变汉堡菜单抽屉
  - 表格行高加大到触摸友好(48px)、按钮最小 44px
  - 输入框 16px 字号(避免 iOS 自动缩放)
- 🚀 **一键启动脚本**
  - `start.sh` — macOS/Linux 一键启动(自动建 venv + 装依赖 + 启动)
  - `start_crm.bat` — Windows 一键启动(升级版,加 PORT env + 依赖检查 + venv 回退)
  - `Makefile` — make run / init / reset / backup / stop
- 🗄️ **数据库自动初始化** — `run.py` 启动时检测 db 是否存在,不存在则自动 init
- 🌐 **浏览器自动打开** — `run.py` 启动后自动打开默认浏览器
- 🔌 **端口可配置** — `PORT=5050 python3 run.py`,默认 5050 避免 macOS ControlCe 占用 5000
- 📖 **README 三平台说明** — macOS/Linux/Windows 各有启动方式

### 修复
- 修复 900px 断点导致平板窗口侧边栏缩成 64px emoji 窄条(无文字提示也无可点)
- 修复 README "启动方法"段重复

### 安全 / 隐私
- 新增 `.gitignore` 严格排除 `instance/*.db` / `instance/backups/` / venv/ / `__pycache__`
- GitHub commit history 清理:DEPLOY.md 中 14 处原 Windows 路径替换为占位符 `C:\Users\<USERNAME>\...`
- 项目上线到公开仓库: <https://github.com/zwm521gmailcom/crm-education>

## [v1.0.0] - 2026-08-11(Windows 端初版)

### 新增
- 🎓 学员 / 联系人 / 课程 / 报名 / 排期 / 考勤 / 收款 / 退费 / 课时流水(8 张核心表 + HourAdjustment + User)
- 🔐 单管理员账号登录(session 7 天)
- 📊 仪表盘:在读学员 / 剩余课时 / 本月营收 / 退费 / 近期排期 / 课时紧张学员
- 📅 排期列表 + 日历视图(周/月)
- ⏱️ 课时手工调整流水(赠送/扣减)
- 📥 Excel 导出(学员/报名/收款/退费)
- 💾 自动备份(`instance/backups/`,每 2 点 cron)

### 技术栈
- Flask 3.0.3 + SQLAlchemy + SQLite + Jinja2 + WTForms + openpyxl
- 12 个蓝图(routes/auth, dashboard, students, courses, enrollments, schedules, calendar, payments, refunds, exports, reports, admin)

---

## 改动类型说明

| 类型 | 含义 |
|------|------|
| **新增** | 新功能 |
| **变更** | 已有功能的改动 |
| **弃用** | 即将移除的功能 |
| **移除** | 已移除的功能 |
| **修复** | Bug 修复 |
| **安全** | 安全/隐私相关 |

## 怎么更新本文件

每次改完代码并 commit 后,在这个文件顶部 `[未发布]` 段加一行,标明日期时再切到正式版本。

**示例**:

```markdown
## [未发布] - 进行中

### 新增
- 学员导出支持 PDF 格式

### 修复
- 排期日历点击空白处报错
```

发布时把 `[未发布]` 改成 `## [v1.2.0] - 2026-08-25`,并在 git 里打 tag:
```bash
git tag -a v1.2.0 -m "v1.2.0: 学员导出 PDF + 日历修复"
git push origin v1.2.0
```

## 版本号规则 (语义化版本 SemVer)

- **主版本号**(v**1**.x.x):不兼容的 API 变更
- **次版本号**(v1.**2**.x):向下兼容的新功能
- **修订号**(v1.2.**3**):向下兼容的 bug 修复

例如:
- `v1.1.0` → `v1.1.1` — 改一个 bug
- `v1.1.1` → `v1.2.0` — 加一个新功能
- `v1.2.0` → `v2.0.0` — 改架构/不兼容升级
