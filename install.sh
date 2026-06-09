#!/bin/bash
# 灵墨一键安装脚本（无需 Docker）
# macOS / Linux
set -e

echo "========================================="
echo "  灵墨 · AI 创作伴侣 — 一键安装"
echo "========================================="

# Download
echo ""
echo "📦 正在下载灵墨..."
curl -L -o lingmo.zip "https://github.com/iccmo/lingmo/archive/refs/heads/main.zip"
unzip -qo lingmo.zip
cd lingmo-main

# Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未安装 Python 3，请先安装：https://www.python.org/downloads/"
    exit 1
fi

# Setup
echo "🔧 正在安装依赖..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q

# API Key
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "🔑 请输入 DeepSeek API Key（没有就回车跳过）:"
    read -r API_KEY
    if [ -n "$API_KEY" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/DEEPSEEK_API_KEY=/DEEPSEEK_API_KEY=${API_KEY}/" .env
        else
            sed -i "s/DEEPSEEK_API_KEY=/DEEPSEEK_API_KEY=${API_KEY}/" .env
        fi
    fi
fi

# Start
echo ""
echo "🚀 正在启动..."
python3 -m uvicorn novel_writer.server:app --host 0.0.0.0 --port 8000 &
sleep 2

echo ""
echo "========================================="
echo "  安装完成！浏览器打开 http://localhost:8000"
echo "========================================="
