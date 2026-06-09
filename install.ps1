# 灵墨一键安装 — PowerShell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  灵墨 · AI 创作伴侣" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 未安装 Python 3，请先下载安装：" -ForegroundColor Red
    Write-Host "   https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "   ⚠️ 安装时务必勾选 Add Python to PATH" -ForegroundColor Yellow
    exit 1
}

Write-Host "📦 正在下载..."
Invoke-WebRequest -Uri "https://github.com/iccmo/lingmo/archive/refs/heads/main.zip" -OutFile "$env:TEMP\lingmo.zip"
Expand-Archive -Force "$env:TEMP\lingmo.zip" "$env:TEMP\lingmo"
Set-Location "$env:TEMP\lingmo\lingmo-main"

Write-Host "🔧 安装依赖（首次约2分钟）..."
python -m venv .venv
.\.venv\Scripts\activate.ps1
pip install -r requirements.txt -q 2>&1 | Out-Null

if (!(Test-Path .env)) {
    Copy-Item .env.example .env
}

Write-Host "🚀 启动中..."
Start-Process "http://localhost:8000"
python -m uvicorn novel_writer.server:app --host 0.0.0.0 --port 8000
