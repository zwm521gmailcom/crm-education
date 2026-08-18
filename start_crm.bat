@echo off
chcp 65001 >nul
title 教培 CRM 启动器
cd /d "%~dp0"

:: 端口可通过环境变量覆盖,默认 5050(避免和部分 Windows 服务的 5000 冲突)
if not defined PORT set "PORT=5050"
set "URL=http://127.0.0.1:%PORT%"

echo ====================================
echo      教培 CRM 启动器 v1.1
echo ====================================
echo   平台: Windows
echo   端口: %PORT%
echo.

:: 选 Python 解释器(优先 venv,没有就回退到系统 python)
set "PY_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0venv\Scripts\python.exe"
    echo [.] 使用虚拟环境: venv\Scripts\python.exe
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_EXE=python"
        echo [.] 未找到 venv,使用系统 python
    ) else (
        echo [X] 未找到 python,请先安装 Python 3.10+
        echo     下载: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:: 检查依赖(快速试一下能不能 import flask)
"%PY_EXE%" -c "import flask" >nul 2>nul
if %errorlevel% neq 0 (
    echo [.] 正在安装依赖 ...
    "%PY_EXE%" -m pip install -q -r requirements.txt
    if %errorlevel% neq 0 (
        echo [X] 依赖安装失败,请手动跑: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

:: 检查端口是否已经在监听
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if %errorlevel%==0 (
    echo [√] 服务已在运行 ^(端口 %PORT%^)
    goto :open_browser
)

echo [.] 正在启动服务,请稍候...
echo     ^(run.py 会自动检测并初始化数据库^)

:: 启动 Flask 服务到新窗口(窗口标题: 教培 CRM - 服务窗口)
:: 用户关闭这个窗口即停止服务
start "教培 CRM - 服务窗口" /D "%~dp0" "%PY_EXE%" "%~dp0run.py"

:: 等待服务起来,最多 20 秒(给 init_db 留时间)
set /a count=0
:wait_loop
set /a count+=1
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if %errorlevel%==0 goto :ready
if %count% geq 20 (
    echo [X] 启动超时,请检查"教培 CRM - 服务窗口"里的错误信息
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_loop

:ready
echo [√] 服务已就绪
:open_browser
start "" "%URL%"
echo [√] 浏览器已打开
echo.
echo 默认账号: admin / admin123
echo 提示:关闭本窗口不影响服务,要停止请关"教培 CRM - 服务窗口"
echo.
timeout /t 3 /nobreak >nul
exit /b 0
