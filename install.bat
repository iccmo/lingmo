@echo off
chcp 65001 >nul
echo =========================================
echo   灵墨 · AI 创作伴侣 — 一键安装
echo =========================================
echo.

:: Check Docker
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 未安装 Docker，请先安装：
    echo    https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo ✅ Docker 已安装

:: Download
echo.
echo 📦 正在下载灵墨...
curl -L -o lingmo.zip "https://github.com/iccmo/lingmo/archive/refs/heads/main.zip"
tar -xf lingmo.zip
cd lingmo-main

:: Configure
if not exist .env (
    echo.
    set /p API_KEY="🔑 请输入 DeepSeek API Key（没有就回车跳过）: "
    copy .env.example .env >nul
    if not "!API_KEY!"=="" (
        powershell -Command "(gc .env) -replace 'DEEPSEEK_API_KEY=', 'DEEPSEEK_API_KEY=!API_KEY!' | Out-File -encoding ASCII .env"
        echo ✅ API Key 已配置
    ) else (
        echo ⚠️  跳过
    )
)

:: Start
echo.
echo 🚀 正在启动...
docker compose up --build -d

echo.
echo =========================================
echo   安装完成！
echo   浏览器打开 http://localhost:8000
echo =========================================
pause
