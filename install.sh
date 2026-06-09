#!/bin/bash
# 灵墨一键安装脚本
# macOS / Linux
set -e

echo "========================================="
echo "  灵墨 · AI 创作伴侣 — 一键安装"
echo "========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装 Docker，请先安装："
    echo "   macOS:  brew install --cask docker"
    echo "   Linux:  curl -fsSL https://get.docker.com | sh"
    exit 1
fi
echo "✅ Docker 已安装"

# Download latest release
REPO="iccmo/lingmo"
echo ""
echo "📦 正在下载灵墨..."
curl -L -o lingmo.zip "https://github.com/${REPO}/archive/refs/heads/main.zip"
unzip -qo lingmo.zip
cd lingmo-main

# Configure
if [ ! -f .env ]; then
    echo ""
    echo "🔑 请输入 DeepSeek API Key（没有就回车跳过，之后在设置页配置）："
    read -r API_KEY
    if [ -n "$API_KEY" ]; then
        cp .env.example .env
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/DEEPSEEK_API_KEY=/DEEPSEEK_API_KEY=${API_KEY}/" .env
        else
            sed -i "s/DEEPSEEK_API_KEY=/DEEPSEEK_API_KEY=${API_KEY}/" .env
        fi
        echo "✅ API Key 已配置"
    else
        cp .env.example .env
        echo "⚠️  跳过，之后在设置页配置"
    fi
fi

# Start
echo ""
echo "🚀 正在启动..."
docker compose up --build -d

echo ""
echo "========================================="
echo "  安装完成！"
echo "  浏览器打开 http://localhost:8000"
echo "========================================="
