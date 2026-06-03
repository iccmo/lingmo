#!/bin/bash
# 灵墨一键启动脚本（含自动重启）
# Usage: ./start.sh

set -e
cd "$(dirname "$0")"

# Clean stale pyc cache
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

echo "=== 灵墨 · AI 创作伴侣 ==="

# Start backend with auto-restart
echo "[backend] Starting on :8000..."
while true; do
    python3 -m uvicorn novel_writer.server:app --host 0.0.0.0 --port 8000
    echo "[backend] Restarting in 2s..."
    sleep 2
done &

# Start frontend
echo "[frontend] Starting on :5200..."
cd frontend
npx vite --host 0.0.0.0 &
cd ..

echo ""
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5200"
echo ""
echo "  Ctrl+C to stop all"

wait
