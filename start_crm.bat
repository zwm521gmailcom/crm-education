@echo off
chcp 65001 >nul
title 教培 CRM 启动器
cd /d "%~dp0"

set "PORT=5000"
set "URL=http://127.0.0.1:%PORT%"

echo ====================================
echo      教培 CRM 启动器 v1.0
echo ====================================
echo.

:: 检查 5000 端口是否已经在监听
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if %errorlevel%==0 (
    echo [√] 服务已在运行 ^(端口 %PORT%^)
    goto :open_browser
)

echo [.] 正在启动服务,请稍候...

:: 启动 Flask 服务到新窗口(窗口标题: 教培 CRM - 服务窗口)
:: 用户关闭这个窗口即停止服务
start "教培 CRM - 服务窗口" /D "%~dp0" "%~dp0venv\Scripts\python.exe" "%~dp0run.py"

:: 等待服务起来,最多 15 秒
set /a count=0
:wait_loop
set /a count+=1
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if %errorlevel%==0 goto :ready
if %count% geq 15 (
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
echo 提示:关闭本窗口不影响服务,要停止请关"教培 CRM - 服务窗口"
echo.
timeout /t 3 /nobreak >nul
exit /b 0
