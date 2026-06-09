@echo off
chcp 65001 >nul
echo =========================================
echo   灵墨 · AI 创作伴侣 — 一键安装
echo =========================================
echo.

:: Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 未安装 Python 3
    echo    请从 https://www.python.org/downloads/ 下载安装
    echo    ⚠️ 安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)
echo ✅ Python 已安装

:: Download
echo.
echo 📦 正在下载...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/iccmo/lingmo/archive/refs/heads/main.zip' -OutFile 'lingmo.zip'"
powershell -Command "Expand-Archive -Force lingmo.zip ."
cd lingmo-main

:: Setup
echo 🔧 正在安装依赖（首次约2分钟）...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: .env
if not exist .env (
    copy .env.example .env >nul
    echo.
    echo 🔑 API Key 可以之后在网站设置页填入，现在跳过
)

:: Start
echo.
echo 🚀 正在启动...
start "" http://localhost:8000
python -m uvicorn novel_writer.server:app --host 0.0.0.0 --port 8000

pause
